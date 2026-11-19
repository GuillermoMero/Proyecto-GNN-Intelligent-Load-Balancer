"""
Router inteligente GNN + RL (primera versión, P1).

Idea
----
* Los servicios se representan como un GRAFO: nodos = instancias/servicios,
  aristas = relaciones de dependencia (o de réplica del mismo servicio).
* Cada nodo tiene un vector de estado: [conexiones activas, latencia EMA, CPU, RAM].
* Una GNN de 2 capas (estilo GraphSAGE, implementada en NumPy) hace message
  passing: cada nodo combina sus propias features con el promedio de sus vecinos.
  La salida es un Q-value por nodo = recompensa esperada de enviar la petición ahí.
* Aprendizaje online (Q-learning con gamma = 0, es decir, bandido contextual):
  tras cada petición se calcula el reward real y se actualizan los pesos con
  backpropagation sobre el nodo elegido.
* Política: softmax sobre los Q-values (temperatura tau) + un epsilon pequeño
  con decaimiento. Con Q muy distintos (réplica congestionada) es casi greedy;
  con Q parecidos reparte el tráfico en lugar de "elegir un favorito" por ruido.

Limitaciones declaradas (se abordan en P2): sin atención propia, reward fijo,
sin horizonte temporal (gamma = 0), grafo pequeño.
"""

import threading
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
        M1 = self.An @ X
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


class IntelligentLoadBalancerEnv:
    FEATURES = ["active_connections", "avg_latency_ms", "cpu_percent", "mem_mb"]
    # Escalas para normalizar cada feature a ~[0, 1]
    SCALES = np.array([10.0, 500.0, 100.0, 256.0])

    def __init__(self, instances, edges=None, seed=42, hidden_dim=16, lr=0.02,
                 eps_start=0.10, eps_min=0.02, eps_decay=0.995, tau=0.2):
        self.instances = list(instances)
        self.n = len(self.instances)
        self.seed = seed
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.tau = tau
        self.eps_start, self.eps_min, self.eps_decay = eps_start, eps_min, eps_decay
        # Por defecto: todas las réplicas del servicio son vecinas entre sí.
        # Al agregar grades-svc/course-svc, aquí se añaden sus aristas reales.
        self.edges = edges if edges is not None else [
            (i, j) for i in range(self.n) for j in range(i + 1, self.n)
        ]
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
            self.metrics = {
                inst: {"active_connections": 0, "avg_latency_ms": 0.0,
                       "cpu_percent": 0.0, "mem_mb": 0.0}
                for inst in self.instances
            }

    # ---- estado ----------------------------------------------------------
    def _features(self):
        X = np.array([[self.metrics[i][f] for f in self.FEATURES] for i in self.instances])
        return np.clip(X / self.SCALES, 0.0, 2.0)

    def set_remote(self, instance, cpu_percent, mem_mb):
        """CPU y RAM reportadas por el /metrics de cada réplica (polling)."""
        with self._lock:
            self.metrics[instance]["cpu_percent"] = float(cpu_percent)
            self.metrics[instance]["mem_mb"] = float(mem_mb)

    # ---- decisión --------------------------------------------------------
    def select_action(self):
        """Devuelve (instancia, contexto). El contexto se usa luego en learn()."""
        with self._lock:
            X = self._features()
            if self.rng.rand() < self.epsilon:
                a = int(self.rng.randint(self.n))
            else:
                q = self.model.forward(X)
                # softmax con temperatura: prob. alta para el mejor Q, pero no 100 %
                z = (q - q.max()) / self.tau
                p = np.exp(z)
                p /= p.sum()
                a = int(self.rng.choice(self.n, p=p))
            self.metrics[self.instances[a]]["active_connections"] += 1
            return self.instances[a], (X, a)

    def on_complete(self, instance, latency_ms, ok):
        """Se llama al terminar la petición (éxito o error)."""
        with self._lock:
            m = self.metrics[instance]
            m["active_connections"] = max(0, m["active_connections"] - 1)
            # Un error cuenta como latencia alta (penalización), NUNCA como 0 ms
            lat = float(latency_ms) if ok else max(float(latency_ms), 1000.0)
            m["avg_latency_ms"] = lat if m["avg_latency_ms"] == 0.0 \
                else m["avg_latency_ms"] * 0.8 + lat * 0.2

    # ---- aprendizaje -----------------------------------------------------
    @staticmethod
    def compute_reward(latency_ms, ok=True):
        if not ok:
            return -10.0
        return -min(float(latency_ms), 1000.0) / 100.0  # 400 ms -> -4.0

    def learn(self, ctx, reward):
        """Q-learning con gamma = 0: acerca Q(nodo elegido) al reward observado."""
        X, a = ctx
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
                "instances": self.instances,
                "features": self.FEATURES,
                "node_state": self.metrics,
                "q_values": {i: float(v) for i, v in zip(self.instances, q)},
                "adjacency": self.adjacency().tolist(),
                "epsilon": round(self.epsilon, 4),
                "tau": self.tau,
                "steps": self.steps,
                "reward_ema": round(self.reward_ema, 3),
            }