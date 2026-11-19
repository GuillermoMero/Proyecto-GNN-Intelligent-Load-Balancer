"""
Router inteligente GNN + RL (primera versión, P1).

Idea
----
* El sistema se representa como un GRAFO DE DEPENDENCIAS:
      nodos   = servicios / instancias (gateway, auth-svc, course-svc, redis,
                user-svc-1, user-svc-2)
      aristas = dependencias reales (gateway -> auth, auth -> redis, ...)
                + una arista entre réplicas del mismo servicio.
* Cada nodo tiene un vector de estado:
      [conexiones activas, latencia EMA, CPU, RAM, es_réplica]
* Una GNN de 2 capas (estilo GraphSAGE, implementada en NumPy) hace message
  passing: cada nodo combina sus propias features con el promedio de sus
  vecinos. Con 2 capas una réplica "ve" hasta 2 saltos: el gateway (1 salto)
  y, a través de él, auth, course y la otra réplica (2 saltos).
* La salida es un Q-value por nodo = recompensa esperada de enviar la petición
  ahí. Solo las réplicas de user-svc son acciones válidas (máscara de acciones);
  el resto de nodos aportan contexto.
* Aprendizaje online (Q-learning con gamma = 0, es decir, bandido contextual):
  tras cada petición se calcula el reward real y se actualizan los pesos con
  backpropagation sobre el nodo elegido.
* Reward = -latencia/100 - LAMBDA * cola_al_elegir.
  El segundo término es el "costo de congestión": enviar a una réplica con
  cola no solo afecta a esta petición, también retrasa a las que ya esperan.
  Sin él, el agente era "egoísta": evitaba la réplica lenta pero saturaba la
  sana.
* Política: softmax sobre los Q-values de las réplicas (temperatura tau) + un
  epsilon pequeño con decaimiento.
* Estado obsoleto: si una réplica deja de recibir tráfico, su latencia EMA
  decae con el tiempo; así el agente la vuelve a probar y detecta si se
  recuperó.

Limitaciones declaradas (se abordan en P2): sin atención propia, reward fijo,
sin horizonte temporal (gamma = 0), grafo pequeño.
"""

import os
import threading
import time

import numpy as np


class GraphQNetwork:
    """GNN de 2 capas tipo GraphSAGE + cabeza lineal que da un Q por nodo."""

    def __init__(self, in_dim, hidden_dim, neigh_matrix, seed=42):
        rng = np.random.RandomState(seed)  # RNG propio: no toca el estado global
        self.An = neigh_matrix.astype(np.float64)  # promedio de vecinos (sin self-loop)
        h = hidden_dim
        he = lambda fan_in, shape: rng.randn(*shape) * np.sqrt(2.0 / fan_in)

        self.Ws1, self.Wn1, self.b1 = he(in_dim, (in_dim, h)), he(in_dim, (in_dim, h)), np.zeros(h)
        self.Ws2, self.Wn2, self.b2 = he(h, (h, h)), he(h, (h, h)), np.zeros(h)
        self.w_out = rng.randn(h) * 0.1
        self.b_out = 0.0

    # ---- forward ---------------------------------------------------------
    def forward(self, X, cache=False):
        M1 = self.An @ X                      # mensaje: promedio de los vecinos
        Z1 = X @ self.Ws1 + M1 @ self.Wn1 + self.b1
        H1 = np.maximum(0, Z1)
        M2 = self.An @ H1
        Z2 = H1 @ self.Ws2 + M2 @ self.Wn2 + self.b2
        H2 = np.maximum(0, Z2)
        q = H2 @ self.w_out + self.b_out
        if cache:
            return q, (X, M1, Z1, H1, M2, Z2, H2)
        return q

    # ---- gradientes de (q[a] - target)^2 ---------------------------------
    def grads(self, X, a, target):
        q, (X, M1, Z1, H1, M2, Z2, H2) = self.forward(X, cache=True)
        err = q[a] - target
        dq = np.zeros_like(q)
        dq[a] = 2.0 * err

        g = {}
        g["w_out"] = H2.T @ dq
        g["b_out"] = dq.sum()
        dH2 = np.outer(dq, self.w_out)
        dZ2 = dH2 * (Z2 > 0)

        g["Ws2"] = H1.T @ dZ2
        g["Wn2"] = M2.T @ dZ2
        g["b2"] = dZ2.sum(axis=0)
        dH1 = dZ2 @ self.Ws2.T + self.An.T @ (dZ2 @ self.Wn2.T)
        dZ1 = dH1 * (Z1 > 0)

        g["Ws1"] = X.T @ dZ1
        g["Wn1"] = M1.T @ dZ1
        g["b1"] = dZ1.sum(axis=0)
        return g, err

    def apply(self, g, lr, clip=1.0):
        norm = np.sqrt(sum(float(np.sum(np.square(v))) for v in g.values()))
        scale = clip / norm if norm > clip else 1.0
        for k, v in g.items():
            setattr(self, k, getattr(self, k) - lr * scale * v)


def build_service_graph(user_instances):
    """
    Topología del SGA (coincide con docker-compose.yml):

        gateway(LB) ── auth-svc ──┐
            │    └──── course-svc ─┴── redis
            ├── user-svc-1
            └── user-svc-2      (user-svc-1 ── user-svc-2: réplicas)

    Devuelve (nombres_de_nodos, aristas, índices_de_réplicas).
    """
    nodes = ["gateway", "auth-svc", "course-svc", "redis"] + list(user_instances)
    idx = {n: i for i, n in enumerate(nodes)}
    edges = [
        (idx["gateway"], idx["auth-svc"]),
        (idx["gateway"], idx["course-svc"]),
        (idx["auth-svc"], idx["redis"]),
        (idx["course-svc"], idx["redis"]),
    ]
    replicas = [idx[u] for u in user_instances]
    for r in replicas:                         # el gateway depende de cada réplica
        edges.append((idx["gateway"], r))
    for i in range(len(replicas)):             # réplicas del mismo servicio
        for j in range(i + 1, len(replicas)):
            edges.append((replicas[i], replicas[j]))
    return nodes, edges, replicas


class IntelligentLoadBalancerEnv:
    FEATURES = ["active_connections", "avg_latency_ms", "cpu_percent", "mem_mb", "is_replica"]
    # Escalas para normalizar cada feature a ~[0, 1]
    SCALES = np.array([10.0, 500.0, 100.0, 256.0, 1.0])

    def __init__(self, instances, seed=42, hidden_dim=16, lr=0.02,
                 eps_start=0.10, eps_min=0.02, eps_decay=0.995, tau=0.3,
                 congestion_lambda=float(os.getenv("GNN_CONGESTION_LAMBDA", "0.1")),
                 stale_after_s=5.0, stale_decay=0.95):
        self.instances = list(instances)                 # réplicas de user-svc
        self.nodes, self.edges, self.action_nodes = build_service_graph(self.instances)
        self.n = len(self.nodes)
        self.seed = seed
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.tau = tau
        self.eps_start, self.eps_min, self.eps_decay = eps_start, eps_min, eps_decay
        # Costo de congestión: cuánto se castiga cada petición ya en cola
        self.congestion_lambda = congestion_lambda
        # Estado obsoleto: tras `stale_after_s` sin tráfico, la latencia EMA
        # de la réplica se multiplica por `stale_decay` en cada llamada
        self.stale_after_s = stale_after_s
        self.stale_decay = stale_decay
        self._lock = threading.RLock()
        self.reset()

    # ---- grafo -----------------------------------------------------------
    def adjacency(self):
        A = np.zeros((self.n, self.n))
        for i, j in self.edges:
            A[i, j] = A[j, i] = 1.0
        return A

    def _neigh_matrix(self):
        A = self.adjacency()
        deg = A.sum(axis=1, keepdims=True)
        return np.divide(A, deg, out=np.zeros_like(A), where=deg > 0)

    # ---- ciclo de vida ---------------------------------------------------
    def reset(self):
        with self._lock:
            self.rng = np.random.RandomState(self.seed)
            self.model = GraphQNetwork(len(self.FEATURES), self.hidden_dim,
                                       self._neigh_matrix(), seed=self.seed)
            self.epsilon = self.eps_start
            self.steps = 0
            self.reward_ema = 0.0
            now = time.time()
            self.metrics = {
                n: {"active_connections": 0, "avg_latency_ms": 0.0,
                    "cpu_percent": 0.0, "mem_mb": 0.0,
                    "is_replica": 1.0 if i in self.action_nodes else 0.0,
                    "last_seen": now}
                for i, n in enumerate(self.nodes)
            }

    # ---- estado ----------------------------------------------------------
    def _features(self):
        X = np.array([[self.metrics[n][f] for f in self.FEATURES] for n in self.nodes])
        return np.clip(X / self.SCALES, 0.0, 2.0)

    def set_remote(self, node, cpu_percent, mem_mb):
        """CPU y RAM reportadas por el /metrics de cada nodo (polling)."""
        with self._lock:
            if node in self.metrics:
                self.metrics[node]["cpu_percent"] = float(cpu_percent)
                self.metrics[node]["mem_mb"] = float(mem_mb)

    def set_latency(self, node, latency_ms):
        """Latencia medida externamente (ej: redis, medida por auth-svc)."""
        with self._lock:
            if node in self.metrics:
                self.metrics[node]["avg_latency_ms"] = float(latency_ms)

    def decay_stale(self):
        """
        Réplicas sin tráfico reciente: su latencia EMA decae poco a poco.
        Así su Q sube y el agente la vuelve a probar; si sigue lenta, la
        latencia real la vuelve a subir de inmediato.
        """
        with self._lock:
            now = time.time()
            for i in self.action_nodes:
                m = self.metrics[self.nodes[i]]
                if m["active_connections"] == 0 and now - m["last_seen"] > self.stale_after_s:
                    m["avg_latency_ms"] *= self.stale_decay

    @staticmethod
    def _ema(m, lat):
        m["avg_latency_ms"] = lat if m["avg_latency_ms"] == 0.0 \
            else m["avg_latency_ms"] * 0.8 + lat * 0.2

    # ---- decisión --------------------------------------------------------
    def select_action(self):
        """Elige una réplica. Devuelve (instancia, contexto para learn())."""
        with self._lock:
            X = self._features()
            cand = self.action_nodes                      # máscara: solo réplicas
            if self.rng.rand() < self.epsilon:
                a = int(cand[self.rng.randint(len(cand))])
            else:
                q = self.model.forward(X)[cand]           # Q solo de las réplicas
                z = (q - q.max()) / self.tau              # softmax con temperatura
                p = np.exp(z)
                p /= p.sum()
                a = int(cand[self.rng.choice(len(cand), p=p)])
            m = self.metrics[self.nodes[a]]
            queue = m["active_connections"]               # cola ANTES de sumar esta
            m["active_connections"] += 1
            self.metrics["gateway"]["active_connections"] += 1
            return self.nodes[a], (X, a, queue)

    def on_complete(self, instance, latency_ms, ok):
        """Se llama UNA vez al terminar la petición (éxito o error)."""
        with self._lock:
            # Un error cuenta como latencia alta (penalización), NUNCA como 0 ms
            lat = float(latency_ms) if ok else max(float(latency_ms), 1000.0)
            now = time.time()
            for name in (instance, "gateway"):
                m = self.metrics[name]
                m["active_connections"] = max(0, m["active_connections"] - 1)
                self._ema(m, lat)
                m["last_seen"] = now

    # ---- aprendizaje -----------------------------------------------------
    @staticmethod
    def compute_reward(latency_ms, ok=True):
        """Reward base (solo latencia). El costo de cola se suma en learn()."""
        if not ok:
            return -10.0
        return -min(float(latency_ms), 1000.0) / 100.0  # 400 ms -> -4.0

    def learn(self, ctx, reward):
        """
        Q-learning con gamma = 0: acerca Q(nodo elegido) al reward observado.
        Al reward base se le resta el costo de congestión (lambda * cola).
        """
        X, a, queue = ctx
        if reward > -10.0:                                # los errores ya tienen -10
            reward = reward - self.congestion_lambda * queue
        with self._lock:
            g, err = self.model.grads(X, a, reward)
            self.model.apply(g, self.lr)
            self.steps += 1
            self.epsilon = max(self.eps_min, self.epsilon * self.eps_decay)
            self.reward_ema = reward if self.steps == 1 else self.reward_ema * 0.95 + reward * 0.05
            return err

    # ---- observabilidad (dashboard) -------------------------------------
    def snapshot(self):
        with self._lock:
            X = self._features()
            q = self.model.forward(X)
            return {
                "nodes": self.nodes,
                "instances": self.instances,
                "features": self.FEATURES,
                # last_seen es interno: no se muestra
                "node_state": {n: {k: v for k, v in m.items() if k != "last_seen"}
                               for n, m in self.metrics.items()},
                "q_values": {self.nodes[i]: float(q[i]) for i in self.action_nodes},
                "edges": [[self.nodes[i], self.nodes[j]] for i, j in self.edges],
                "adjacency": self.adjacency().tolist(),
                "epsilon": round(self.epsilon, 4),
                "tau": self.tau,
                "congestion_lambda": self.congestion_lambda,
                "steps": self.steps,
                "reward_ema": round(self.reward_ema, 3),
            }