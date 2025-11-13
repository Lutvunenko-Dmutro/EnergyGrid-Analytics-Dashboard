import networkx as nx
import pandas as pd
import random
import networkx.algorithms.community as nx_comm 
import networkx.algorithms.flow as nx_flow
from collections import defaultdict

def _parse_voltage(v_str):
    if not v_str: return 0
    try: return max(int(v) for v in v_str.split(';'))
    except (ValueError, TypeError): return 0

def load_and_prepare_data(file_name):
    G_full = nx.read_graphml(file_name)
    components = sorted(nx.connected_components(G_full), key=len, reverse=True)
    G_main = G_full.subgraph(components[0]).copy()
    return G_main

def get_degree_analysis(G):
    full_sorted_degree = sorted(G.degree(), key=lambda item: item[1], reverse=True)
    vulnerable_nodes = [node for node, degree in G.degree() if degree == 1]
    return full_sorted_degree, vulnerable_nodes

def get_centrality_analysis(G):
    print("  ...рахую не-зважену центральність (~30 сек)...")
    centrality = nx.betweenness_centrality(G, k=1000, normalized=True)
    return sorted(centrality.items(), key=lambda item: item[1], reverse=True)

def get_weighted_centrality_analysis(G):
    G_weighted = G.copy()
    for u, v, data in G_weighted.edges(data=True):
        length_str = data.get('lengthm')
        try: data['weight'] = float(length_str)
        except (ValueError, TypeError, AttributeError): data['weight'] = 1.0
    print("  ...рахую зважену центральність (~30 сек)...")
    centrality = nx.betweenness_centrality(G_weighted, k=1000, normalized=True, weight='weight')
    return sorted(centrality.items(), key=lambda item: item[1], reverse=True)

def get_histogram_data(G):
    print("  ...готую дані для гістограми...")
    hist_list = nx.degree_histogram(G)
    df = pd.DataFrame({'Ступінь': range(len(hist_list)), 'Кількість вузлів': hist_list})
    df = df[df['Ступінь'] > 0] 
    return df

def calculate_robustness(G, nodes_to_attack):
    sizes = []; G_copy = G.copy(); initial_size = float(G_copy.number_of_nodes()); sizes.append(1.0) 
    total = len(nodes_to_attack)
    for i, node in enumerate(nodes_to_attack):
        if i % 10 == 0: print(f"    ...прогрес стійкості: {i}/{total}", end='\r')
        if node not in G_copy:
            if sizes: sizes.append(sizes[-1]); continue
        G_copy.remove_node(node)
        if G_copy.number_of_nodes() == 0: sizes.append(0.0); continue
        largest_comp_nodes = max(nx.connected_components(G_copy), key=len)
        sizes.append(len(largest_comp_nodes) / initial_size)
    print(f"    ...прогрес стійкості: {total}/{total} - Завершено.")
    df = pd.DataFrame({'Крок атаки': range(len(sizes)), 'Розмір мережі (%)': [s * 100 for s in sizes]})
    return df

def get_voltage_data_for_nodes(G):
    print("  ...аналізую напругу для 9418 вузлів...")
    node_voltages = defaultdict(int)
    for u, v, data in G.edges(data=True):
        voltage = _parse_voltage(data.get('voltage'))
        if voltage > node_voltages[u]: node_voltages[u] = voltage
        if voltage > node_voltages[v]: node_voltages[v] = voltage
    node_data = {'lat': [], 'lon': [], 'text': [], 'category': [], 'id': []}
    for node, data in G.nodes(data=True):
        lon_str = data.get('lon'); lat_str = data.get('lat')
        if not (lon_str and lat_str): continue
        try: lat = float(lat_str); lon = float(lon_str)
        except (ValueError, TypeError): continue
        max_v = node_voltages[node]
        if max_v >= 380000: category = "380кВ+"
        elif max_v >= 220000: category = "220кВ"
        elif max_v >= 110000: category = "110кВ"
        else: category = "Інше (<110кВ)"
        node_data['lat'].append(lat); node_data['lon'].append(lon)
        node_data['text'].append(f"ID: {node}<br>Max V: {max_v/1000:.0f}кВ<br>Lat: {lat:.4f}<br>Lon: {lon:.4f}")
        node_data['category'].append(category); node_data['id'].append(node)
    return pd.DataFrame(node_data)

def get_bottleneck_analysis(G, source_node, sink_node):
    print(f"  ...рахую вузьке місце: {source_node} -> {sink_node}...")
    G_capacity = G.copy()
    for u, v, data in G_capacity.edges(data=True):
        length_str = data.get('lengthm')
        try:
            length = float(length_str)
            if length == 0: data['capacity'] = 1.0
            else: data['capacity'] = 1.0 / length
        except (ValueError, TypeError, AttributeError):
            data['capacity'] = 1.0
            
    cut_value, partition = nx_flow.minimum_cut(G_capacity, source_node, sink_node, capacity='capacity')
    reachable, non_reachable = partition
    bottleneck_edges = nx.edge_boundary(G_capacity, reachable, non_reachable)
    
    bottleneck_data = []
    min_voltage = float('inf')
    
    for u, v in bottleneck_edges:
        edge_data = G_capacity.edges[u, v]
        voltage_str = edge_data.get('voltage', '0')
        voltage_num = _parse_voltage(voltage_str)
        if voltage_num > 0 and voltage_num < min_voltage:
            min_voltage = voltage_num
        bottleneck_data.append((f"{u} - {v}", voltage_str, f"{float(edge_data.get('lengthm', 0)):.1f} м"))
        
    if min_voltage == float('inf'): min_voltage = 0
        
    df = pd.DataFrame(bottleneck_data, columns=["ЛЕП (Від - До)", "Напруга (V)", "Довжина (м)"])
    
    stats = {
        'cut_value_str': f"{cut_value:,.6f}", 
        'line_count': len(df),
        'min_voltage_str': f"{min_voltage/1000:.0f} кВ" if min_voltage > 0 else "N/A"
    }
    
    return stats, df 

def get_communities_analysis(G):
    print("  ...рахую спільноти...")
    communities_sets = nx_comm.louvain_communities(G, seed=42)
    communities_list = sorted(communities_sets, key=len, reverse=True)
    community_data = [(f"Спільнота #{i+1}", f"{len(community)} вузлів") for i, community in enumerate(communities_list[:15])]
    return pd.DataFrame(community_data, columns=["Назва спільноти", "Розмір"]), len(communities_list)

def get_hubs_voltage_composition(G, top_10_hubs_list):
    print("  ...аналізую склад Топ-10 Хабів...")
    hub_composition_data = []
    for hub_id, degree in top_10_hubs_list:
        counts = {"380кВ+": 0, "220кВ": 0, "110кВ": 0, "Інше": 0}
        for neighbor in G.neighbors(hub_id):
            edge_data = G.edges[hub_id, neighbor]
            max_v = _parse_voltage(edge_data.get('voltage'))
            if max_v >= 380000: counts["380кВ+"] += 1
            elif max_v >= 220000: counts["220кВ"] += 1
            elif max_v >= 110000: counts["110кВ"] += 1
            else: counts["Інше"] += 1
        for category, count in counts.items():
            if count > 0:
                hub_composition_data.append({'hub_id': f"#{top_10_hubs_list.index((hub_id, degree))+1}: {hub_id} ({degree} ЛЕП)", 'Категорія напруги': category, 'Кількість ЛЕП': count})
    return pd.DataFrame(hub_composition_data)