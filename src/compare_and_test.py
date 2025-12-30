"""
Compare Rule Quality & Test Cold-Start Recommendations
Analyzes graph-based vs traditional Apriori and validates transitivity
"""

import json
import os
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
import numpy as np

from graph_based_apriori import CooccurrenceGraph


class RuleQualityComparison:
    """Compare traditional vs graph-based rules"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        
        # Load graph-based rules
        with open(os.path.join(output_dir, 'rules.json'), 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
            self.graph_rules = rules_data['rules']
            self.graph_metadata = rules_data['metadata']
        
        print(f"✓ Loaded graph-based rules: {len(self.graph_rules)} rules")
        
        # Try to load old traditional rules if they exist
        self.traditional_rules = None
        old_rules_path = os.path.join(output_dir, 'rules_traditional.json')
        if os.path.exists(old_rules_path):
            with open(old_rules_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                self.traditional_rules = old_data.get('rules', [])
            print(f"✓ Loaded traditional rules: {len(self.traditional_rules)} rules")
        else:
            print("⚠ No traditional rules found for comparison")
    
    def compare_basic_statistics(self) -> Dict[str, Any]:
        """Compare basic statistics"""
        print("\n" + "="*70)
        print("BASIC STATISTICS COMPARISON")
        print("="*70)
        
        stats = {'graph_based': self._analyze_rules(self.graph_rules)}
        
        if self.traditional_rules:
            stats['traditional'] = self._analyze_rules(self.traditional_rules)
            
            # Calculate improvements
            stats['improvements'] = {
                'total_rules': f"{(len(self.graph_rules) / len(self.traditional_rules)):.2f}x" 
                              if self.traditional_rules else "N/A",
                'avg_confidence': f"{(stats['graph_based']['avg_confidence'] - stats['traditional']['avg_confidence']):.4f}",
                'avg_lift': f"{(stats['graph_based']['avg_lift'] - stats['traditional']['avg_lift']):.4f}"
            }
        
        # Print comparison
        self._print_statistics_table(stats)
        
        return stats
    
    def _analyze_rules(self, rules: List[Dict]) -> Dict[str, Any]:
        """Analyze a set of rules"""
        if not rules:
            return {}
        
        supports = [r['support'] for r in rules]
        confidences = [r['confidence'] for r in rules]
        lifts = [r['lift'] for r in rules]
        
        # Itemset lengths
        ant_lengths = [r['antecedent_len'] for r in rules]
        
        # Product coverage
        all_products = set()
        for rule in rules:
            all_products.update(rule['antecedents'])
            all_products.update(rule['consequents'])
        
        return {
            'total_rules': len(rules),
            'avg_support': float(np.mean(supports)),
            'avg_confidence': float(np.mean(confidences)),
            'avg_lift': float(np.mean(lifts)),
            'max_lift': float(np.max(lifts)),
            'min_confidence': float(np.min(confidences)),
            'product_coverage': len(all_products),
            'rules_by_antecedent_len': dict(Counter(ant_lengths)),
            'high_confidence_rules': sum(1 for c in confidences if c >= 0.8),
            'high_lift_rules': sum(1 for l in lifts if l >= 2.0)
        }
    
    def _print_statistics_table(self, stats: Dict[str, Any]):
        """Print comparison table"""
        print("\n📊 Rule Quality Metrics:")
        print("-" * 70)
        
        if 'traditional' in stats:
            print(f"{'Metric':<30} {'Traditional':>15} {'Graph-Based':>15} {'Change':>10}")
            print("-" * 70)
            
            metrics = [
                ('Total Rules', 'total_rules'),
                ('Avg Support', 'avg_support'),
                ('Avg Confidence', 'avg_confidence'),
                ('Avg Lift', 'avg_lift'),
                ('Max Lift', 'max_lift'),
                ('Product Coverage', 'product_coverage'),
                ('High Confidence (≥0.8)', 'high_confidence_rules'),
                ('High Lift (≥2.0)', 'high_lift_rules')
            ]
            
            for label, key in metrics:
                trad = stats['traditional'].get(key, 0)
                graph = stats['graph_based'].get(key, 0)
                
                if isinstance(trad, float):
                    change = f"{((graph - trad) / trad * 100):+.1f}%" if trad != 0 else "N/A"
                    print(f"{label:<30} {trad:>15.4f} {graph:>15.4f} {change:>10}")
                else:
                    change = f"{((graph - trad) / trad * 100):+.1f}%" if trad != 0 else "N/A"
                    print(f"{label:<30} {trad:>15} {graph:>15} {change:>10}")
        else:
            # Only graph-based
            g = stats['graph_based']
            print(f"Total Rules:           {g['total_rules']}")
            print(f"Avg Confidence:        {g['avg_confidence']:.4f}")
            print(f"Avg Lift:              {g['avg_lift']:.4f}")
            print(f"Max Lift:              {g['max_lift']:.4f}")
            print(f"Product Coverage:      {g['product_coverage']}")
            print(f"High Confidence:       {g['high_confidence_rules']}")
            print(f"High Lift:             {g['high_lift_rules']}")
        
        print("-" * 70)
        
        # Antecedent length distribution
        print(f"\n📈 Rule Complexity Distribution (Graph-Based):")
        for length, count in sorted(stats['graph_based']['rules_by_antecedent_len'].items()):
            pct = count / stats['graph_based']['total_rules'] * 100
            print(f"  {length}-itemset antecedents: {count:>5} rules ({pct:>5.1f}%)")
    
    def analyze_rule_overlap(self) -> Dict[str, Any]:
        """Analyze rule overlap between methods"""
        if not self.traditional_rules:
            return {}
        
        print("\n" + "="*70)
        print("RULE OVERLAP ANALYSIS")
        print("="*70)
        
        # Create rule signatures
        def make_signature(rule):
            ants = tuple(sorted(rule['antecedents']))
            cons = tuple(sorted(rule['consequents']))
            return (ants, cons)
        
        trad_sigs = {make_signature(r) for r in self.traditional_rules}
        graph_sigs = {make_signature(r) for r in self.graph_rules}
        
        overlap = trad_sigs & graph_sigs
        only_trad = trad_sigs - graph_sigs
        only_graph = graph_sigs - trad_sigs
        
        overlap_data = {
            'shared_rules': len(overlap),
            'only_traditional': len(only_trad),
            'only_graph': len(only_graph),
            'overlap_percentage': len(overlap) / len(trad_sigs) * 100 if trad_sigs else 0
        }
        
        print(f"\n🔗 Rule Overlap:")
        print(f"  Shared by both:      {overlap_data['shared_rules']} rules")
        print(f"  Only traditional:    {overlap_data['only_traditional']} rules")
        print(f"  Only graph-based:    {overlap_data['only_graph']} rules")
        print(f"  Overlap %:           {overlap_data['overlap_percentage']:.1f}%")
        
        return overlap_data
    
    def find_top_rules(self, metric: str = 'lift', top_n: int = 10) -> List[Dict]:
        """Find top rules by metric"""
        sorted_rules = sorted(self.graph_rules, key=lambda r: r[metric], reverse=True)
        return sorted_rules[:top_n]
    
    def print_top_rules(self, top_n: int = 10):
        """Print top rules by different metrics"""
        print("\n" + "="*70)
        print(f"TOP {top_n} RULES BY DIFFERENT METRICS")
        print("="*70)
        
        for metric in ['lift', 'confidence', 'support']:
            print(f"\n🏆 Top {top_n} by {metric.upper()}:")
            top_rules = self.find_top_rules(metric, top_n)
            
            for i, rule in enumerate(top_rules, 1):
                ants = ', '.join(rule['antecedents'])
                cons = ', '.join(rule['consequents'])
                print(f"  {i:2d}. [{ants}] → [{cons}]")
                print(f"      Support: {rule['support']:.4f}, "
                      f"Confidence: {rule['confidence']:.4f}, "
                      f"Lift: {rule['lift']:.4f}")


class ColdStartTester:
    """Test cold-start recommendations using transitivity"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        
        # Load co-occurrence graph
        graph_path = os.path.join(output_dir, 'cooccurrence_graph.json')
        self.cooccurrence_graph = CooccurrenceGraph.load_graph(graph_path)
        
        # Load training data for product names
        train_path = os.path.join(output_dir, 'train.json')
        with open(train_path, 'r', encoding='utf-8') as f:
            self.train_records = json.load(f)
        
        # Build product ID to name mapping
        self.product_names = {}
        for record in self.train_records:
            pid = record.get('product_id')
            name = record.get('service_name', f'Product_{pid}')
            if pid and pid not in self.product_names:
                self.product_names[pid] = name
        
        print(f"✓ Loaded co-occurrence graph for cold-start testing")
    
    def test_cold_start_scenarios(self) -> None:
        """Test various cold-start scenarios"""
        print("\n" + "="*70)
        print("COLD-START RECOMMENDATION TESTING")
        print("="*70)
        
        # Select test products (popular ones)
        node_counts = [(node, data['count']) 
                      for node, data in self.cooccurrence_graph.graph.nodes(data=True)]
        top_products = sorted(node_counts, key=lambda x: x[1], reverse=True)[:10]
        
        print(f"\n🎯 Testing transitive recommendations for top 10 products:")
        
        for i, (product_id, count) in enumerate(top_products, 1):
            product_name = self.product_names.get(product_id, product_id)
            
            print(f"\n{i}. Product: {product_name} (ID: {product_id}, Count: {count})")
            
            # Get transitive recommendations
            recommendations = self.cooccurrence_graph.find_transitive_recommendations(
                product_id, max_distance=2
            )
            
            if recommendations:
                print(f"   Found {len(recommendations)} transitive recommendations:")
                
                # Show top recommendations
                top_recs = recommendations[:8]
                
                for j, (target, score) in enumerate(top_recs, 1):
                    target_name = self.product_names.get(target, target)
                    
                    # Determine if direct neighbor
                    is_direct = self.cooccurrence_graph.graph.has_edge(product_id, target)
                    marker = "●" if is_direct else "○"
                    
                    print(f"   {marker} {j}. {target_name}: {score:.2f}")
                
                # Count direct vs transitive
                direct_count = sum(1 for t, _ in recommendations 
                                  if self.cooccurrence_graph.graph.has_edge(product_id, t))
                transitive_count = len(recommendations) - direct_count
                
                print(f"   └─ ({direct_count} direct ●, {transitive_count} transitive ○)")
            else:
                print(f"   ⚠ No transitive recommendations found (isolated node?)")
    
    def test_specific_path(self, source: str, target: str) -> None:
        """Test specific transitive path between two products"""
        print("\n" + "="*70)
        print("TRANSITIVE PATH ANALYSIS")
        print("="*70)
        
        import networkx as nx
        
        source_name = self.product_names.get(source, source)
        target_name = self.product_names.get(target, target)
        
        print(f"\n🔍 Finding path: {source_name} → {target_name}")
        
        try:
            # Check if direct edge exists
            if self.cooccurrence_graph.graph.has_edge(source, target):
                weight = self.cooccurrence_graph.graph[source][target]['weight']
                print(f"   ✓ Direct connection exists (weight: {weight})")
            else:
                print(f"   ⚠ No direct connection")
            
            # Find shortest path
            if nx.has_path(self.cooccurrence_graph.graph, source, target):
                path = nx.shortest_path(self.cooccurrence_graph.graph, source, target)
                
                print(f"\n   Shortest path ({len(path)-1} hops):")
                for i in range(len(path) - 1):
                    curr = path[i]
                    next_node = path[i + 1]
                    weight = self.cooccurrence_graph.graph[curr][next_node]['weight']
                    
                    curr_name = self.product_names.get(curr, curr)
                    next_name = self.product_names.get(next_node, next_node)
                    
                    print(f"   {i+1}. {curr_name} →[{weight}]→ {next_name}")
                
                # Calculate transitive score
                total_weight = sum(
                    self.cooccurrence_graph.graph[path[i]][path[i+1]]['weight']
                    for i in range(len(path) - 1)
                )
                distance = len(path) - 1
                score = total_weight / (distance ** 2) if distance > 0 else total_weight
                
                print(f"\n   Transitive score: {score:.2f}")
                print(f"   (Total weight: {total_weight}, Distance: {distance})")
            else:
                print(f"   ✗ No path exists between these products")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    def analyze_graph_connectivity(self) -> Dict[str, Any]:
        """Analyze graph connectivity for cold-start coverage"""
        print("\n" + "="*70)
        print("GRAPH CONNECTIVITY ANALYSIS")
        print("="*70)
        
        import networkx as nx
        
        G = self.cooccurrence_graph.graph
        
        # Basic connectivity
        is_connected = nx.is_connected(G)
        num_components = nx.number_connected_components(G)
        
        if not is_connected:
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            component_sizes = [len(c) for c in components]
        else:
            largest_component = set(G.nodes())
            component_sizes = [len(G.nodes())]
        
        # Calculate average path lengths in largest component
        largest_subgraph = G.subgraph(largest_component)
        try:
            avg_path_length = nx.average_shortest_path_length(largest_subgraph)
        except:
            avg_path_length = float('inf')
        
        # Diameter (longest shortest path)
        try:
            diameter = nx.diameter(largest_subgraph)
        except:
            diameter = float('inf')
        
        connectivity = {
            'is_connected': is_connected,
            'num_components': num_components,
            'largest_component_size': len(largest_component),
            'component_sizes': component_sizes,
            'avg_path_length': avg_path_length,
            'diameter': diameter,
            'coverage_percentage': len(largest_component) / G.number_of_nodes() * 100
        }
        
        print(f"\n🌐 Graph Connectivity:")
        print(f"  Connected:              {'Yes' if is_connected else 'No'}")
        print(f"  Number of components:   {num_components}")
        print(f"  Largest component:      {len(largest_component)} nodes "
              f"({connectivity['coverage_percentage']:.1f}%)")
        
        if not is_connected:
            print(f"  Component sizes:        {sorted(component_sizes, reverse=True)[:5]}")
        
        if avg_path_length != float('inf'):
            print(f"  Avg path length:        {avg_path_length:.2f} hops")
        if diameter != float('inf'):
            print(f"  Diameter:               {diameter} hops")
        
        print(f"\n💡 Cold-Start Implications:")
        if connectivity['coverage_percentage'] >= 90:
            print(f"  ✓ Excellent coverage - transitive recommendations available for "
                  f"{connectivity['coverage_percentage']:.1f}% of products")
        elif connectivity['coverage_percentage'] >= 70:
            print(f"  ⚠ Good coverage - some products may lack transitive recommendations")
        else:
            print(f"  ⚠ Limited coverage - graph fragmented, cold-start challenging")
        
        return connectivity


def main():
    """Main comparison and testing"""
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    
    print("="*70)
    print("GRAPH-BASED APRIORI: QUALITY COMPARISON & COLD-START TESTING")
    print("="*70)
    
    # Part 1: Rule Quality Comparison
    print("\n" + "="*70)
    print("PART 1: RULE QUALITY COMPARISON")
    print("="*70)
    
    comparator = RuleQualityComparison(output_dir)
    stats = comparator.compare_basic_statistics()
    
    if comparator.traditional_rules:
        overlap = comparator.analyze_rule_overlap()
    
    comparator.print_top_rules(top_n=5)
    
    # Part 2: Cold-Start Testing
    print("\n" + "="*70)
    print("PART 2: COLD-START RECOMMENDATION TESTING")
    print("="*70)
    
    tester = ColdStartTester(output_dir)
    
    # Test connectivity
    connectivity = tester.analyze_graph_connectivity()
    
    # Test transitive recommendations
    tester.test_cold_start_scenarios()
    
    # Test specific paths (if graph is well connected)
    if connectivity['is_connected'] or connectivity['coverage_percentage'] > 80:
        print("\n" + "="*70)
        print("EXAMPLE: TRANSITIVE PATH ANALYSIS")
        print("="*70)
        
        # Get two random products from largest component
        import random
        nodes = list(tester.cooccurrence_graph.graph.nodes())
        if len(nodes) >= 2:
            source, target = random.sample(nodes[:50], 2)  # From popular products
            tester.test_specific_path(source, target)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n✓ Graph-Based Apriori Results:")
    print(f"  • Rules generated: {len(comparator.graph_rules)}")
    print(f"  • Product coverage: {stats['graph_based']['product_coverage']} products")
    print(f"  • Avg confidence: {stats['graph_based']['avg_confidence']:.4f}")
    print(f"  • Avg lift: {stats['graph_based']['avg_lift']:.4f}")
    
    print(f"\n✓ Cold-Start Capabilities:")
    print(f"  • Graph coverage: {connectivity['coverage_percentage']:.1f}%")
    if connectivity['avg_path_length'] != float('inf'):
        print(f"  • Avg recommendation path: {connectivity['avg_path_length']:.2f} hops")
    print(f"  • Transitive recommendations: Available for most products")
    
    print(f"\n🎯 Conclusion:")
    if connectivity['coverage_percentage'] >= 90:
        print(f"  Graph-based approach provides excellent cold-start coverage!")
        print(f"  Transitive paths enable recommendations even without direct co-occurrence.")
    else:
        print(f"  Graph-based approach provides good cold-start support,")
        print(f"  but some products may benefit from additional features.")


if __name__ == '__main__':
    main()
