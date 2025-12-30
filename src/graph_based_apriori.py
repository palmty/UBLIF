"""
Graph-Based Incremental Apriori
Using co-occurrence graph for real-time incremental learning
"""

import json
import networkx as nx
from collections import defaultdict
from itertools import combinations
from typing import List, Dict, Set, Tuple, Any
import numpy as np


class CooccurrenceGraph:
    """
    Global co-occurrence graph for incremental pattern mining
    Nodes = Products, Edges = Co-occurrences, Weights = Frequencies
    """
    
    def __init__(self, min_support: float = 0.001, min_confidence: float = 0.3, min_lift: float = 1.2):
        """
        Initialize co-occurrence graph
        
        Args:
            min_support: Minimum support threshold (ratio)
            min_confidence: Minimum confidence threshold
            min_lift: Minimum lift threshold
        """
        self.graph = nx.Graph()  # Undirected graph for co-occurrence
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        
        self.total_transactions = 0
        self.metadata = defaultdict(dict)  # Store product metadata
        
    def add_transaction(self, products: List[str], metadata: Dict[str, Any] = None) -> None:
        """
        Incrementally add a single transaction to the graph
        This is the key to incremental learning!
        
        Args:
            products: List of product IDs in the transaction
            metadata: Optional metadata (category, timestamp, etc.)
        """
        if len(products) < 2:
            return  # Skip single-item transactions
        
        self.total_transactions += 1
        
        # Update node counts (1-itemsets)
        for product in products:
            if product not in self.graph:
                self.graph.add_node(product, count=0, metadata={})
            
            self.graph.nodes[product]['count'] += 1
            
            # Update metadata if provided
            if metadata and product in metadata:
                self.graph.nodes[product]['metadata'] = metadata[product]
        
        # Update edge weights (2-itemsets) - all pairs
        for prod_a, prod_b in combinations(products, 2):
            if self.graph.has_edge(prod_a, prod_b):
                self.graph[prod_a][prod_b]['weight'] += 1
            else:
                self.graph.add_edge(prod_a, prod_b, weight=1)
    
    def batch_add_transactions(self, transactions: List[List[str]], 
                               metadata_list: List[Dict] = None) -> None:
        """
        Add multiple transactions at once
        
        Args:
            transactions: List of product lists
            metadata_list: Optional list of metadata dicts
        """
        print(f"Adding {len(transactions)} transactions to graph...")
        
        for i, products in enumerate(transactions):
            meta = metadata_list[i] if metadata_list else None
            self.add_transaction(products, meta)
        
        print(f"✓ Graph updated: {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges, "
              f"{self.total_transactions} total transactions")
    
    def get_frequent_1_itemsets(self) -> List[Tuple[str, float]]:
        """
        Find frequent 1-itemsets (products) from graph nodes
        
        Returns:
            List of (product, support) tuples
        """
        frequent_items = []
        
        for product, data in self.graph.nodes(data=True):
            support = data['count'] / self.total_transactions
            if support >= self.min_support:
                frequent_items.append((product, support))
        
        return sorted(frequent_items, key=lambda x: x[1], reverse=True)
    
    def get_frequent_2_itemsets(self) -> List[Tuple[Tuple[str, str], float]]:
        """
        Find frequent 2-itemsets (pairs) from graph edges
        
        Returns:
            List of ((product_a, product_b), support) tuples
        """
        frequent_pairs = []
        
        for prod_a, prod_b, data in self.graph.edges(data=True):
            support = data['weight'] / self.total_transactions
            if support >= self.min_support:
                frequent_pairs.append(((prod_a, prod_b), support))
        
        return sorted(frequent_pairs, key=lambda x: x[1], reverse=True)
    
    def find_triangles(self) -> List[Tuple[str, str, str]]:
        """
        Find all triangles (3-cliques) in the graph
        Triangle = 3 products that all co-occur with each other
        
        Returns:
            List of (product_a, product_b, product_c) tuples
        """
        triangles = []
        
        # Use NetworkX triangle finding
        triangle_dict = nx.triangles(self.graph)
        
        # Extract unique triangles
        visited = set()
        for node, triangle_count in triangle_dict.items():
            if triangle_count == 0:
                continue
            
            # Get neighbors to find actual triangles
            neighbors = list(self.graph.neighbors(node))
            for i, n1 in enumerate(neighbors):
                for n2 in neighbors[i+1:]:
                    # Check if n1 and n2 are connected (forming triangle)
                    if self.graph.has_edge(n1, n2):
                        # Sort to avoid duplicates
                        triangle = tuple(sorted([node, n1, n2]))
                        if triangle not in visited:
                            visited.add(triangle)
                            triangles.append(triangle)
        
        return triangles
    
    def get_frequent_3_itemsets(self) -> List[Tuple[Tuple[str, str, str], float]]:
        """
        Find frequent 3-itemsets using triangle finding
        Much faster than traditional Apriori join!
        
        Returns:
            List of ((prod_a, prod_b, prod_c), support) tuples
        """
        frequent_triples = []
        triangles = self.find_triangles()
        
        for triangle in triangles:
            prod_a, prod_b, prod_c = triangle
            
            # Calculate support as min edge weight
            # (conservative estimate - actual co-occurrence might be higher)
            weight_ab = self.graph[prod_a][prod_b]['weight']
            weight_bc = self.graph[prod_b][prod_c]['weight']
            weight_ac = self.graph[prod_a][prod_c]['weight']
            
            # Use minimum weight as conservative support estimate
            min_weight = min(weight_ab, weight_bc, weight_ac)
            support = min_weight / self.total_transactions
            
            if support >= self.min_support:
                frequent_triples.append((triangle, support))
        
        return sorted(frequent_triples, key=lambda x: x[1], reverse=True)
    
    def generate_rules_from_graph(self) -> List[Dict[str, Any]]:
        """
        Generate association rules directly from graph structure
        No need to scan transactions!
        
        Returns:
            List of rule dictionaries
        """
        rules = []
        
        # Generate 2-itemset rules (A → B)
        for prod_a, prod_b, edge_data in self.graph.edges(data=True):
            weight_ab = edge_data['weight']
            count_a = self.graph.nodes[prod_a]['count']
            count_b = self.graph.nodes[prod_b]['count']
            
            support = weight_ab / self.total_transactions
            
            if support < self.min_support:
                continue
            
            # Rule: A → B
            confidence_a_to_b = weight_ab / count_a
            lift_a_to_b = (weight_ab / self.total_transactions) / \
                         ((count_a / self.total_transactions) * 
                          (count_b / self.total_transactions))
            
            if confidence_a_to_b >= self.min_confidence and lift_a_to_b >= self.min_lift:
                rules.append({
                    'antecedents': [prod_a],
                    'consequents': [prod_b],
                    'support': float(support),
                    'confidence': float(confidence_a_to_b),
                    'lift': float(lift_a_to_b),
                    'antecedent_len': 1,
                    'consequent_len': 1
                })
            
            # Rule: B → A (symmetric)
            confidence_b_to_a = weight_ab / count_b
            lift_b_to_a = lift_a_to_b  # Lift is symmetric
            
            if confidence_b_to_a >= self.min_confidence and lift_b_to_a >= self.min_lift:
                rules.append({
                    'antecedents': [prod_b],
                    'consequents': [prod_a],
                    'support': float(support),
                    'confidence': float(confidence_b_to_a),
                    'lift': float(lift_b_to_a),
                    'antecedent_len': 1,
                    'consequent_len': 1
                })
        
        # Generate 3-itemset rules from triangles
        frequent_triples = self.get_frequent_3_itemsets()
        
        for triangle, support in frequent_triples:
            prod_a, prod_b, prod_c = triangle
            
            # Generate rules: {A,B} → C, {A,C} → B, {B,C} → A
            for antecedent_pair in [(prod_a, prod_b), (prod_a, prod_c), (prod_b, prod_c)]:
                consequent = [p for p in triangle if p not in antecedent_pair][0]
                
                # Get edge weight for antecedent pair
                weight_pair = self.graph[antecedent_pair[0]][antecedent_pair[1]]['weight']
                
                # Calculate confidence
                confidence = support * self.total_transactions / weight_pair
                
                # Calculate lift
                count_c = self.graph.nodes[consequent]['count']
                lift = support / ((weight_pair / self.total_transactions) * 
                                 (count_c / self.total_transactions))
                
                if confidence >= self.min_confidence and lift >= self.min_lift:
                    rules.append({
                        'antecedents': list(antecedent_pair),
                        'consequents': [consequent],
                        'support': float(support),
                        'confidence': float(confidence),
                        'lift': float(lift),
                        'antecedent_len': 2,
                        'consequent_len': 1
                    })
        
        print(f"✓ Generated {len(rules)} rules from graph")
        return rules
    
    def find_transitive_recommendations(self, product: str, max_distance: int = 2) -> List[Tuple[str, float]]:
        """
        Find recommendations using graph transitivity (cold start solution!)
        
        Example:
            User likes iPhone
            iPhone → Case (direct)
            Case → Film (direct)
            Therefore: recommend Film to iPhone user (transitive)
        
        Args:
            product: Source product
            max_distance: Maximum path length
            
        Returns:
            List of (recommended_product, score) tuples
        """
        if product not in self.graph:
            return []
        
        recommendations = defaultdict(float)
        
        # BFS to find products within max_distance
        for target in self.graph.nodes():
            if target == product:
                continue
            
            try:
                path = nx.shortest_path(self.graph, product, target)
                distance = len(path) - 1
                
                if distance <= max_distance:
                    # Calculate score: inverse of distance, weighted by edge weights
                    score = 0
                    for i in range(len(path) - 1):
                        weight = self.graph[path[i]][path[i+1]]['weight']
                        score += weight / (distance ** 2)  # Penalize longer paths
                    
                    recommendations[target] = score
            except nx.NetworkXNoPath:
                continue
        
        # Sort by score
        return sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    
    def get_product_clusters(self, resolution: float = 1.0) -> Dict[str, int]:
        """
        Find product communities/clusters using graph community detection
        
        Args:
            resolution: Resolution parameter for community detection
            
        Returns:
            Dict mapping product to cluster ID
        """
        from networkx.algorithms import community
        
        # Use Louvain method for community detection
        communities = community.louvain_communities(self.graph, resolution=resolution)
        
        product_to_cluster = {}
        for cluster_id, cluster in enumerate(communities):
            for product in cluster:
                product_to_cluster[product] = cluster_id
        
        return product_to_cluster
    
    def save_graph(self, filepath: str) -> None:
        """
        Save graph to disk for persistence
        
        Args:
            filepath: Path to save graph (JSON format)
        """
        graph_data = {
            'nodes': [
                {
                    'id': node,
                    'count': data['count'],
                    'metadata': data.get('metadata', {})
                }
                for node, data in self.graph.nodes(data=True)
            ],
            'edges': [
                {
                    'source': u,
                    'target': v,
                    'weight': data['weight']
                }
                for u, v, data in self.graph.edges(data=True)
            ],
            'total_transactions': self.total_transactions,
            'parameters': {
                'min_support': self.min_support,
                'min_confidence': self.min_confidence,
                'min_lift': self.min_lift
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Graph saved to {filepath}")
    
    @classmethod
    def load_graph(cls, filepath: str) -> 'CooccurrenceGraph':
        """
        Load graph from disk
        
        Args:
            filepath: Path to load graph from
            
        Returns:
            CooccurrenceGraph instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        
        # Create instance
        params = graph_data['parameters']
        instance = cls(
            min_support=params['min_support'],
            min_confidence=params['min_confidence'],
            min_lift=params['min_lift']
        )
        
        # Restore graph
        for node_data in graph_data['nodes']:
            instance.graph.add_node(
                node_data['id'],
                count=node_data['count'],
                metadata=node_data['metadata']
            )
        
        for edge_data in graph_data['edges']:
            instance.graph.add_edge(
                edge_data['source'],
                edge_data['target'],
                weight=edge_data['weight']
            )
        
        instance.total_transactions = graph_data['total_transactions']
        
        print(f"✓ Graph loaded from {filepath}")
        print(f"  Nodes: {instance.graph.number_of_nodes()}")
        print(f"  Edges: {instance.graph.number_of_edges()}")
        print(f"  Transactions: {instance.total_transactions}")
        
        return instance


def demo_incremental_learning():
    """
    Demonstrate incremental learning capability
    """
    print("="*70)
    print("DEMO: Graph-Based Incremental Apriori")
    print("="*70)
    
    # Initialize graph
    graph = CooccurrenceGraph(min_support=0.2, min_confidence=0.5, min_lift=1.2)
    
    # Initial transactions
    print("\n[1] Adding initial transactions...")
    initial_transactions = [
        ['iPhone', 'Case'],
        ['iPhone', 'Charger'],
        ['Case', 'Film'],
        ['iPhone', 'Case', 'Film'],
        ['Charger', 'Cable'],
    ]
    graph.batch_add_transactions(initial_transactions)
    
    # Generate rules
    print("\n[2] Generating rules from initial data...")
    rules_v1 = graph.generate_rules_from_graph()
    print(f"Initial rules: {len(rules_v1)}")
    for rule in rules_v1[:5]:
        print(f"  {rule['antecedents']} → {rule['consequents']} "
              f"(conf: {rule['confidence']:.2f}, lift: {rule['lift']:.2f})")
    
    # Incremental update
    print("\n[3] ⚡ INCREMENTAL UPDATE (new transactions)...")
    new_transactions = [
        ['iPhone', 'Film'],  # New pattern!
        ['Case', 'Film', 'Charger'],
        ['iPhone', 'Case', 'Charger'],
    ]
    graph.batch_add_transactions(new_transactions)
    
    # Generate updated rules (no retrain!)
    print("\n[4] Generating rules from updated graph...")
    rules_v2 = graph.generate_rules_from_graph()
    print(f"Updated rules: {len(rules_v2)} (+{len(rules_v2) - len(rules_v1)})")
    
    # Show transitive recommendations
    print("\n[5] 🔗 Transitive recommendations (Cold Start)...")
    recommendations = graph.find_transitive_recommendations('iPhone', max_distance=2)
    print(f"Recommendations for 'iPhone' users:")
    for product, score in recommendations[:5]:
        print(f"  {product}: {score:.2f}")
    
    print("\n✓ Demo completed!")


if __name__ == '__main__':
    demo_incremental_learning()
