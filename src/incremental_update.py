"""
Incremental Update Script
Add new transactions to co-occurrence graph without full retrain
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

from graph_based_apriori import CooccurrenceGraph
from custom_predictor import CustomPredictor, ModelTrainer
import networkx as nx


class IncrementalUpdater:
    """
    Handle incremental updates to co-occurrence graph
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize updater
        
        Args:
            output_dir: Path to outputs directory with existing graph
        """
        self.output_dir = output_dir
        self.graph_path = os.path.join(output_dir, 'cooccurrence_graph.json')
        self.rules_path = os.path.join(output_dir, 'rules.json')
        
        # Load existing co-occurrence graph
        print("Loading existing co-occurrence graph...")
        self.cooccurrence_graph = CooccurrenceGraph.load_graph(self.graph_path)
        print(f"✓ Loaded graph: {self.cooccurrence_graph.graph.number_of_nodes()} nodes, "
              f"{self.cooccurrence_graph.graph.number_of_edges()} edges, "
              f"{self.cooccurrence_graph.total_transactions} transactions")
        
        # Load training data for metadata
        train_path = os.path.join(output_dir, 'train.json')
        with open(train_path, 'r', encoding='utf-8') as f:
            self.train_records = json.load(f)
    
    def add_new_transactions(self, new_transactions: List[List[str]]) -> Dict[str, Any]:
        """
        Add new transactions to graph incrementally
        
        Args:
            new_transactions: List of product lists
            
        Returns:
            Update statistics
        """
        print("\n=== INCREMENTAL UPDATE ===")
        
        # Get stats before
        nodes_before = self.cooccurrence_graph.graph.number_of_nodes()
        edges_before = self.cooccurrence_graph.graph.number_of_edges()
        transactions_before = self.cooccurrence_graph.total_transactions
        
        start_time = datetime.now()
        
        # Add transactions incrementally (O(k²) per transaction)
        for transaction in new_transactions:
            self.cooccurrence_graph.add_transaction(transaction)
        
        update_time = (datetime.now() - start_time).total_seconds() * 1000  # milliseconds
        
        # Get stats after
        nodes_after = self.cooccurrence_graph.graph.number_of_nodes()
        edges_after = self.cooccurrence_graph.graph.number_of_edges()
        transactions_after = self.cooccurrence_graph.total_transactions
        
        stats = {
            'transactions_added': len(new_transactions),
            'nodes_added': nodes_after - nodes_before,
            'edges_added': edges_after - edges_before,
            'update_time_ms': update_time,
            'avg_time_per_transaction_ms': update_time / len(new_transactions) if new_transactions else 0,
            'before': {
                'nodes': nodes_before,
                'edges': edges_before,
                'transactions': transactions_before
            },
            'after': {
                'nodes': nodes_after,
                'edges': edges_after,
                'transactions': transactions_after
            }
        }
        
        print(f"\n✓ Update completed in {update_time:.2f}ms")
        print(f"  Transactions: {transactions_before} → {transactions_after} (+{len(new_transactions)})")
        print(f"  Nodes: {nodes_before} → {nodes_after} (+{nodes_after - nodes_before})")
        print(f"  Edges: {edges_before} → {edges_after} (+{edges_after - edges_before})")
        print(f"  Avg time per transaction: {stats['avg_time_per_transaction_ms']:.2f}ms")
        
        return stats
    
    def regenerate_rules(self) -> List[Dict[str, Any]]:
        """
        Regenerate association rules from updated graph
        
        Returns:
            List of rules
        """
        print("\n=== REGENERATING RULES ===")
        
        start_time = datetime.now()
        rules = self.cooccurrence_graph.generate_rules_from_graph()
        generation_time = (datetime.now() - start_time).total_seconds() * 1000
        
        print(f"✓ Generated {len(rules)} rules in {generation_time:.2f}ms")
        
        return rules
    
    def rebuild_prediction_model(self, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rebuild prediction model with updated rules
        
        Args:
            rules: Association rules
            
        Returns:
            Evaluation metrics
        """
        print("\n=== REBUILDING PREDICTION MODEL ===")
        
        # Build directed graph
        G = nx.DiGraph()
        for rule in rules:
            for ant in rule['antecedents']:
                if ant not in G:
                    if ant in self.cooccurrence_graph.graph:
                        count = self.cooccurrence_graph.graph.nodes[ant]['count']
                        G.add_node(ant, count=count)
            
            for cons in rule['consequents']:
                if cons not in G:
                    if cons in self.cooccurrence_graph.graph:
                        count = self.cooccurrence_graph.graph.nodes[cons]['count']
                        G.add_node(cons, count=count)
            
            for ant in rule['antecedents']:
                for cons in rule['consequents']:
                    G.add_edge(ant, cons,
                             confidence=rule['confidence'],
                             lift=rule['lift'],
                             weight=rule['confidence'] * rule['lift'])
        
        # Calculate graph features
        try:
            pagerank = nx.pagerank(G, max_iter=100)
        except:
            pagerank = {node: 1.0/G.number_of_nodes() for node in G.nodes()}
        
        nodes_list = []
        for node in G.nodes():
            in_edges = list(G.in_edges(node, data=True))
            out_edges = list(G.out_edges(node, data=True))
            
            import numpy as np
            node_data = {
                'product_id': node,
                'in_degree': len(in_edges),
                'out_degree': len(out_edges),
                'pagerank': float(pagerank.get(node, 0)),
                'avg_confidence': float(np.mean([e[2]['confidence'] for e in in_edges])) if in_edges else 0.0,
                'avg_lift': float(np.mean([e[2]['lift'] for e in in_edges])) if in_edges else 0.0,
            }
            
            # Add metadata
            product_records = [r for r in self.train_records if r.get('product_id') == node]
            if product_records:
                node_data['category'] = product_records[0].get('category')
                node_data['service_name'] = product_records[0].get('service_name')
            
            nodes_list.append(node_data)
        
        edges_list = []
        for u, v, data in G.edges(data=True):
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
                'total_edges': len(edges_list)
            }
        }
        
        # Train predictor
        trainer = ModelTrainer(rules, graph_structure, self.train_records)
        metrics = trainer.train_on_train_set()
        
        print(f"✓ Model rebuilt")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  ROC-AUC: {metrics['roc_auc']:.4f}")
        
        return {
            'rules': rules,
            'graph': graph_structure,
            'metrics': metrics,
            'predictor': trainer.predictor
        }
    
    def save_updated_model(self, model_data: Dict[str, Any], update_stats: Dict[str, Any]) -> None:
        """
        Save updated model and statistics
        
        Args:
            model_data: Model data (rules, graph, metrics, predictor)
            update_stats: Update statistics
        """
        print("\n=== SAVING UPDATED MODEL ===")
        
        # Save updated rules
        rules_output = {
            'metadata': {
                'algorithm': 'graph_based_apriori',
                'approach': 'incremental_learning',
                'incremental': True,
                'total_rules': len(model_data['rules']),
                'total_products': len(model_data['graph']['nodes']),
                'last_updated': datetime.now().isoformat(),
                'update_stats': update_stats
            },
            'rules': model_data['rules'],
            'graph': model_data['graph']
        }
        
        with open(self.rules_path, 'w', encoding='utf-8') as f:
            json.dump(rules_output, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved rules.json")
        
        # Save updated co-occurrence graph
        self.cooccurrence_graph.save_graph(self.graph_path)
        print(f"✓ Saved cooccurrence_graph.json")
        
        # Update model_config
        config_path = os.path.join(self.output_dir, 'model_config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            model_config = json.load(f)
        
        model_config['prediction']['weights'] = model_data['predictor'].weights
        model_config['prediction']['threshold'] = model_data['predictor'].threshold
        model_config['last_updated'] = datetime.now().isoformat()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(model_config, f, indent=2, ensure_ascii=False)
        print(f"✓ Updated model_config.json")
        
        # Save evaluation metrics
        eval_path = os.path.join(self.output_dir, 'train_evaluation.json')
        with open(eval_path, 'r', encoding='utf-8') as f:
            evaluation = json.load(f)
        
        evaluation['metrics'] = model_data['metrics']
        evaluation['timestamp'] = datetime.now().isoformat()
        evaluation['incremental_update'] = update_stats
        
        with open(eval_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        print(f"✓ Updated train_evaluation.json")
    
    def update_with_new_data(self, new_transactions: List[List[str]]) -> None:
        """
        Complete incremental update workflow
        
        Args:
            new_transactions: List of new product lists
        """
        print("="*70)
        print("INCREMENTAL UPDATE WORKFLOW")
        print("="*70)
        
        total_start = datetime.now()
        
        # Step 1: Add transactions to graph (incremental)
        update_stats = self.add_new_transactions(new_transactions)
        
        # Step 2: Regenerate rules (fast - no DB scan)
        rules = self.regenerate_rules()
        
        # Step 3: Rebuild prediction model
        model_data = self.rebuild_prediction_model(rules)
        
        # Step 4: Save everything
        self.save_updated_model(model_data, update_stats)
        
        total_time = (datetime.now() - total_start).total_seconds() * 1000
        
        print("\n" + "="*70)
        print("INCREMENTAL UPDATE COMPLETED!")
        print("="*70)
        print(f"Total time: {total_time:.2f}ms")
        print(f"Transactions added: {len(new_transactions)}")
        print(f"Rules updated: {len(rules)}")
        print(f"✓ System updated without full retrain!")


def demo_incremental_update():
    """
    Demo: Simulate incremental update with new transactions
    """
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    
    # Initialize updater
    updater = IncrementalUpdater(output_dir)
    
    # Simulate 10 new transactions
    print("\n" + "="*70)
    print("DEMO: SIMULATING 10 NEW TRANSACTIONS")
    print("="*70)
    
    # Generate realistic new transactions from existing products
    import random
    existing_products = list(updater.cooccurrence_graph.graph.nodes())
    
    new_transactions = []
    for i in range(10):
        # Random 2-5 products per transaction
        transaction_size = random.randint(2, 5)
        transaction = random.sample(existing_products, transaction_size)
        new_transactions.append(transaction)
        print(f"Transaction {i+1}: {transaction}")
    
    # Run incremental update
    updater.update_with_new_data(new_transactions)
    
    print("\n✓ Demo completed! Graph updated incrementally.")


if __name__ == '__main__':
    demo_incremental_update()
