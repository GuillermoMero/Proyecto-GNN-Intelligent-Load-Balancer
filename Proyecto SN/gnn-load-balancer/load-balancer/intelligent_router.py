import time
import random
import numpy as np

class GNNQNetworkNumPy:
    def __init__(self, input_dim=2, hidden_dim=16):
        # Inicialización de pesos y sesgos con Xavier/He initialization simulada
        np.random.seed(42)
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros((hidden_dim,))
        
        self.W2 = np.random.randn(hidden_dim, hidden_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros((hidden_dim,))
        
        self.W_out = np.random.randn(hidden_dim, 1) * np.sqrt(2.0 / hidden_dim)
        b_out_val = 0.0
        self.b_out = np.array([b_out_val])

    def relu(self, x):
        return np.maximum(0, x)

    def forward(self, node_features):
        """
        Realiza la inferencia hacia adelante (Feed-forward) emulando una GNN:
        node_features: Matriz con forma [num_nodos, input_dim]
        """
        h1 = self.relu(np.dot(node_features, self.W1) + self.b1)
        h2 = self.relu(np.dot(h1, self.W2) + self.b2)
        scores = np.dot(h2, self.W_out) + self.b_out
        return scores.squeeze(-1)


class IntelligentLoadBalancerEnv:
    def __init__(self, user_instances):
        self.user_instances = user_instances
        self.state_metrics = {
            inst: {"active_connections": 0, "avg_latency": 0.0} 
            for inst in user_instances
        }
        
        # Instanciamos la red neuronal ligera basada en NumPy
        self.model = GNNQNetworkNumPy(input_dim=2, hidden_dim=16)
        self.epsilon = 0.1  # Factor de exploración Epsilon-greedy

    def get_state(self):
        return self.state_metrics

    def select_action(self, state):
        """
        Selecciona el nodo óptimo usando inferencia neuronal ultrarrápida.
        """
        if random.random() < self.epsilon:
            return random.choice(self.user_instances)

        # Preparar características del nodo para la red
        features = []
        for inst in self.user_instances:
            conn = float(state[inst]["active_connections"])
            lat = float(state[inst]["avg_latency"])
            features.append([conn, lat])

        node_features_array = np.array(features, dtype=np.float32)
        
        # Inferencia neuronal
        q_scores = self.model.forward(node_features_array)
        best_idx = int(np.argmin(q_scores)) # Selecciona el nodo con menor penalización estimada Q

        return self.user_instances[best_idx]

    def compute_reward(self, latency):
        if latency < 50:
            return 10.0
        elif latency < 150:
            return 2.0
        else:
            return -float(latency) / 50.0

    def update_metrics(self, instance, latency, active_delta):
        self.state_metrics[instance]["active_connections"] = max(
            0, self.state_metrics[instance]["active_connections"] + active_delta
        )
        current_avg = self.state_metrics[instance]["avg_latency"]
        if current_avg == 0.0:
            self.state_metrics[instance]["avg_latency"] = float(latency)
        else:
            self.state_metrics[instance]["avg_latency"] = (current_avg * 0.8) + (float(latency) * 0.2)