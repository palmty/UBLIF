"""
Phase 2: Graph-Based Apriori (Incremental Version)
Replaces traditional Apriori with graph-based incremental learning
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict
from tqdm import tqdm

from graph_based_apriori import CooccurrenceGraph
from custom_predictor import CustomPredictor, ModelTrainer
import networkx as nx
import numpy as np


class GraphAprioriPipeline:
    """
    Phase 2 pipeline using Graph-Based Incremental Apriori
    """
    
    def __init__(self, config_path: str, train_path: str, output_dir: str):
        """
        Initialize pipeline
        
        Args:
            config_path: Path to config.yaml
            train_path: Path to train.json
            output_dir: Path to outputs directory
        """
        import yaml
        
        self.config_path = config_path
        self.train_path = train_path
        self.output_dir = output_dir
        
        # Load config
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Graph parameters
        self.min_support = 0.001
        self.min_confidence = 0.3
        self.min_lift = 1.2
        
        # Initialize co-occurrence graph
        self.cooccurrence_graph = CooccurrenceGraph(
            min_support=self.min_support,
            min_confidence=self.min_confidence,
            min_lift=self.min_lift
        )
        
        print("Graph-Based Apriori Pipeline initialized!")
    
    def load_train_data(self) -> List[Dict[str, Any]]:
        """Load training data"""
        with open(self.train_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        return records
    
    def prepare_transactions(self, records: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Group records into session-based transactions
        
        Args:
            records: Training records
            
        Returns:
            List of product lists (transactions)
        """
        print("Grouping records into transactions...")
        
        sessions = defaultdict(list)
        for record in records:
            session_id = record.get('session_id')
            product_id = record.get('product_id')
            
            if session_id and product_id:
                sessions[session_id].append(str(product_id))
        
        # Remove duplicates and filter by length
        transactions = []
        for session_id, products in sessions.items():
            unique_products = list(dict.fromkeys(products))
            if len(unique_products) >= 2:  # At least 2 products
                transactions.append(unique_products)
        
        print(f"✓ Created {len(transactions)} transactions from {len(sessions)} sessions")
        return transactions
    
    def build_graph_from_transactions(self, transactions: List[List[str]]) -> None:
        """
        Build co-occurrence graph from transactions
        
        Args:
            transactions: List of product lists
        """
        print("\n=== BUILDING CO-OCCURRENCE GRAPH ===")
        self.cooccurrence_graph.batch_add_transactions(transactions)
        
        # Show graph statistics
        print(f"\nGraph Statistics:")
        print(f"  - Nodes (products): {self.cooccurrence_graph.graph.number_of_nodes()}")
        print(f"  - Edges (co-occurrences): {self.cooccurrence_graph.graph.number_of_edges()}")
        print(f"  - Total transactions: {self.cooccurrence_graph.total_transactions}")
        print(f"  - Average degree: {sum(dict(self.cooccurrence_graph.graph.degree()).values()) / self.cooccurrence_graph.graph.number_of_nodes():.2f}")
    
    def mine_rules_from_graph(self) -> List[Dict[str, Any]]:
        """
        Mine association rules from graph structure
        
        Returns:
            List of rules
        """
        print("\n=== MINING RULES FROM GRAPH ===")
        
        # Show frequent itemsets
        freq_1 = self.cooccurrence_graph.get_frequent_1_itemsets()
        freq_2 = self.cooccurrence_graph.get_frequent_2_itemsets()
        freq_3 = self.cooccurrence_graph.get_frequent_3_itemsets()
        
        print(f"Frequent itemsets:")
        print(f"  - 1-itemsets: {len(freq_1)}")
        print(f"  - 2-itemsets: {len(freq_2)}")
        print(f"  - 3-itemsets: {len(freq_3)}")
        
        # Generate rules
        rules = self.cooccurrence_graph.generate_rules_from_graph()
        
        print(f"\n✓ Generated {len(rules)} association rules")
        return rules
    
    def build_directed_graph_for_prediction(self, rules: List[Dict[str, Any]]) -> nx.DiGraph:
        """
        Build directed graph from rules for prediction
        
        Args:
            rules: Association rules
            
        Returns:
            Directed graph
        """
        print("\n=== BUILDING PREDICTION GRAPH ===")
        
        G = nx.DiGraph()
        
        # Add nodes and edges from rules
        for rule in rules:
            antecedents = rule['antecedents']
            consequents = rule['consequents']
            confidence = rule['confidence']
            lift = rule['lift']
            
            # Add nodes
            for ant in antecedents:
                if ant not in G:
                    # Get node data from co-occurrence graph
                    if ant in self.cooccurrence_graph.graph:
                        count = self.cooccurrence_graph.graph.nodes[ant]['count']
                        G.add_node(ant, count=count)
                    else:
                        G.add_node(ant, count=1)
            
            for cons in consequents:
                if cons not in G:
                    if cons in self.cooccurrence_graph.graph:
                        count = self.cooccurrence_graph.graph.nodes[cons]['count']
                        G.add_node(cons, count=count)
                    else:
                        G.add_node(cons, count=1)
            
            # Add edges
            for ant in antecedents:
                for cons in consequents:
                    weight = confidence * lift
                    G.add_edge(ant, cons, 
                             confidence=confidence,
                             lift=lift,
                             weight=weight)
        
        print(f"✓ Prediction graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G
    
    def calculate_graph_features(self, graph: nx.DiGraph, train_records: List[Dict]) -> Dict[str, Any]:
        """Calculate graph-based features"""
        print("\n=== CALCULATING GRAPH FEATURES ===")
        
        nodes_list = []
        
        # Calculate PageRank
        try:
            pagerank = nx.pagerank(graph, max_iter=100)
        except:
            pagerank = {node: 1.0/graph.number_of_nodes() for node in graph.nodes()}
        
        for node in graph.nodes():
            in_edges = list(graph.in_edges(node, data=True))
            out_edges = list(graph.out_edges(node, data=True))
            
            node_data = {
                'product_id': node,
                'in_degree': len(in_edges),
                'out_degree': len(out_edges),
                'pagerank': float(pagerank.get(node, 0)),
                'avg_confidence': float(np.mean([e[2]['confidence'] for e in in_edges])) if in_edges else 0.0,
                'avg_lift': float(np.mean([e[2]['lift'] for e in in_edges])) if in_edges else 0.0,
            }
            
            # Add metadata from training data
            product_records = [r for r in train_records if r.get('product_id') == node]
            if product_records:
                node_data['category'] = product_records[0].get('category')
                node_data['service_name'] = product_records[0].get('service_name')
                node_data['total_sessions'] = len(product_records)
                node_data['avg_interest_rate'] = np.mean([r.get('interest', 0) for r in product_records])
            
            nodes_list.append(node_data)
        
        edges_list = []
        for u, v, data in graph.edges(data=True):
            edges_list.append({
                'source': u,
                'target': v,
                'weight': float(data['weight']),
                'confidence': float(data['confidence']),
                'lift': float(data['lift'])
            })
        
        graph_structure = {
            'nodes': nodes_list,
            'edges': edges_list,
            'metadata': {
                'total_nodes': len(nodes_list),
                'total_edges': len(edges_list),
                'graph_density': nx.density(graph) if len(nodes_list) > 1 else 0
            }
        }
        
        print(f"✓ Graph features calculated")
        return graph_structure
    
    def calculate_statistics(self, train_records: List[Dict], graph_structure: Dict) -> Dict:
        """Calculate training statistics"""
        print("\n=== CALCULATING STATISTICS ===")
        
        # Graph stats
        nodes = graph_structure['nodes']
        graph_stats = {
            'max_in_degree': max(n['in_degree'] for n in nodes) if nodes else 1,
            'max_out_degree': max(n['out_degree'] for n in nodes) if nodes else 1,
            'max_pagerank': max(n['pagerank'] for n in nodes) if any(n['pagerank'] > 0 for n in nodes) else 1.0,
            'total_nodes': len(nodes),
            'total_edges': graph_structure['metadata']['total_edges']
        }
        
        # Session stats
        durations = [r.get('session_duration_minutes', 0) for r in train_records]
        depths = [r.get('session_depth', 0) for r in train_records]
        positions = [r.get('click_position', 0) for r in train_records]
        
        session_stats = {
            'max_duration': max(durations) if durations else 1.0,
            'max_click_position': max(positions) if positions else 1,
            'max_session_depth': max(depths) if depths else 1,
            'avg_session_length': np.mean([len(r.get('previous_products', [])) for r in train_records])
        }
        
        # Category stats
        category_data = defaultdict(lambda: {'count': 0, 'interest_sum': 0})
        for record in train_records:
            category = record.get('category')
            if category:
                category_data[category]['count'] += 1
                category_data[category]['interest_sum'] += record.get('interest', 0)
        
        category_stats = {}
        for category, data in category_data.items():
            category_stats[category] = {
                'count': data['count'],
                'avg_interest': data['interest_sum'] / max(data['count'], 1)
            }
        
        # Global baseline
        interest_count = sum(1 for r in train_records if r.get('interest') == 1)
        global_baseline = interest_count / len(train_records) if train_records else 0.0
        
        statistics = {
            'graph_stats': graph_stats,
            'session_stats': session_stats,
            'category_stats': category_stats,
            'global_baseline': global_baseline
        }
        
        print(f"✓ Statistics calculated")
        return statistics
    
    def run_full_pipeline(self) -> None:
        """Run complete Graph-Based Apriori pipeline"""
        print("="*70)
        print("PHASE 2: GRAPH-BASED APRIORI (INCREMENTAL)")
        print("="*70)
        
        start_time = datetime.now()
        
        # Load data
        print("\n[1/6] Loading training data...")
        train_records = self.load_train_data()
        print(f"✓ Loaded {len(train_records)} records")
        
        # Prepare transactions
        print("\n[2/6] Preparing transactions...")
        transactions = self.prepare_transactions(train_records)
        
        # Build co-occurrence graph
        print("\n[3/6] Building co-occurrence graph...")
        self.build_graph_from_transactions(transactions)
        
        # Mine rules from graph
        print("\n[4/6] Mining association rules from graph...")
        rules_list = self.mine_rules_from_graph()
        
        if not rules_list:
            print("ERROR: No rules generated!")
            return
        
        # Build prediction graph
        print("\n[5/6] Building prediction graph...")
        prediction_graph = self.build_directed_graph_for_prediction(rules_list)
        graph_structure = self.calculate_graph_features(prediction_graph, train_records)
        
        # Calculate statistics
        print("\n[6/6] Calculating statistics...")
        statistics = self.calculate_statistics(train_records, graph_structure)
        
        # Train predictor
        print("\n=== TRAINING CUSTOM PREDICTOR ===")
        trainer = ModelTrainer(rules_list, graph_structure, train_records)
        train_metrics = trainer.train_on_train_set()
        
        # Save everything
        print("\n=== SAVING OUTPUTS ===")
        self._save_outputs(rules_list, graph_structure, statistics, train_metrics, trainer.predictor)
        
        # Save co-occurrence graph for incremental updates
        graph_path = os.path.join(self.output_dir, 'cooccurrence_graph.json')
        self.cooccurrence_graph.save_graph(graph_path)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*70)
        print("PHASE 2 COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"Total time: {duration:.2f} seconds")
        print(f"Approach: Graph-Based Incremental Apriori")
        print(f"✓ Ready for incremental updates!")
    
    def _save_outputs(self, rules, graph, statistics, metrics, predictor):
        """Save all outputs"""
        # rules.json
        rules_output = {
            'metadata': {
                'algorithm': 'graph_based_apriori',
                'approach': 'incremental_learning',
                'incremental': True,
                'min_support': self.min_support,
                'min_confidence': self.min_confidence,
                'min_lift': self.min_lift,
                'total_rules': len(rules),
                'total_products': len(graph['nodes']),
                'generated_at': datetime.now().isoformat()
            },
            'rules': rules,
            'graph': graph
        }
        
        with open(os.path.join(self.output_dir, 'rules.json'), 'w', encoding='utf-8') as f:
            json.dump(rules_output, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved rules.json")
        
        # model_config.json
        model_config = {
            'version': '2.0',
            'prediction': {
                'method': 'custom_gradient_boosting',
                'weights': predictor.weights,
                'activation': 'sigmoid',
                'threshold': predictor.threshold
            },
            'normalization': statistics,
            'cold_start': {
                'strategy': 'graph_transitivity',
                'baseline_value': statistics['global_baseline']
            }
        }
        
        with open(os.path.join(self.output_dir, 'model_config.json'), 'w', encoding='utf-8') as f:
            json.dump(model_config, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved model_config.json")
        
        # train_statistics.json
        with open(os.path.join(self.output_dir, 'train_statistics.json'), 'w', encoding='utf-8') as f:
            json.dump(statistics, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved train_statistics.json")
        
        # train_evaluation.json
        evaluation = {'metrics': metrics, 'timestamp': datetime.now().isoformat()}
        with open(os.path.join(self.output_dir, 'train_evaluation.json'), 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved train_evaluation.json")


def main():
    """Main entry point"""
    config_path = '/Users/lab1/Documents/ACGI/config.yaml'
    train_path = '/Users/lab1/Documents/ACGI/outputs/train.json'
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    
    pipeline = GraphAprioriPipeline(config_path, train_path, output_dir)
    pipeline.run_full_pipeline()


if __name__ == '__main__':
    main()
