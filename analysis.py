import networkx as nx
import pandas as pd
import random
import networkx.algorithms.community as nx_comm 
import networkx.algorithms.flow as nx_flow
from collections import defaultdict

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def _parse_voltage(v_str):
    """
    Допоміжна функція для безпечного парсингу рядків напруги.
    Вхідні дані можуть бути '380000' або '380000;110000' (кілька ліній).
    
    @param v_str (str): Рядок з атрибуту 'voltage'.
    @return (int): Максимальне значення напруги, знайдене у рядку, або 0.
    """
    if not v_str: 
        return 0
    try: 
        # Розділяємо рядок по ';' і беремо максимальне числове значення
        return max(int(v) for v in v_str.split(';'))
    except (ValueError, TypeError):
        # Повертаємо 0, якщо дані пошкоджені або не є числом
        return 0

# --- 1. ФУНКЦІЯ ЗАВАНТАЖЕННЯ ---

def load_and_prepare_data(file_name):
    """
    Завантажує файл .graphml та готує його до аналізу.
    
    Головне завдання - очистити граф, виділивши лише найбільший
    зв'язний компонент, оскільки більшість графових алгоритмів
    (centrality, flow) некоректно працюють на незв'язних графах.
    
    @param file_name (str): Шлях до файлу .graphml.
    @return (nx.Graph): Очищений, зв'язний граф NetworkX.
    """
    # Завантажуємо повний граф з усіма компонентами
    G_full = nx.read_graphml(file_name)
    
    # Знаходимо всі окремі компоненти (острови)
    components = sorted(nx.connected_components(G_full), key=len, reverse=True)
    
    # Виділяємо найбільший компонент (нашу основну мережу)
    G_main = G_full.subgraph(components[0]).copy()
    
    return G_main

# --- 2. АНАЛІЗ: ХАБИ І ТУПИКИ ---

def get_degree_analysis(G):
    """
    Проводить аналіз ступенів (Degree Centrality) для всіх вузлів.
    Ідентифікує вузли-хаби (високий ступінь) та "тупикові" вузли (ступінь 1).
    
    @param G (nx.Graph): Робочий граф.
    @return (list, list):
        1. full_sorted_degree: Повний список пар (node_id, degree), відсортований.
        2. vulnerable_nodes: Список ID "тупикових" вузлів (ступінь == 1).
    """
    # 1. Отримуємо повний список (node_id, degree) і сортуємо
    full_sorted_degree = sorted(G.degree(), key=lambda item: item[1], reverse=True)
    
    # 2. Знаходимо "тупикові" вузли
    vulnerable_nodes = [node for node, degree in G.degree() if degree == 1]
    
    return full_sorted_degree, vulnerable_nodes

# --- 3. АНАЛІЗ: КРИТИЧНІСТЬ (НЕЗВАЖЕНА) ---

def get_centrality_analysis(G):
    """
    Розраховує незважену центральність за посередництвом (Betweenness Centrality).
    Визначає вузли, що найчастіше лежать на *топологічно* найкоротших шляхах.
    
    @param G (nx.Graph): Робочий граф.
    @return (list): Відсортований список пар (node_id, centrality_score).
    """
    print("  ...рахую не-зважену центральність (~30 сек)...")
    
    # k=1000 використовує апроксимацію (вибірку з 1000 вузлів) для прискорення.
    # Повний розрахунок на ~9k вузлів зайняв би години.
    centrality = nx.betweenness_centrality(G, k=1000, normalized=True)
    
    return sorted(centrality.items(), key=lambda item: item[1], reverse=True)

# --- 4. АНАЛІЗ: КРИТИЧНІСТЬ (ЗВАЖЕНА) ---

def get_weighted_centrality_analysis(G):
    """
    Розраховує зважену центральність за посередництвом (Betweenness Centrality).
    Використовує 'lengthm' (довжину ЛЕП) як вагу.
    Шукає вузли, що лежать на *фізично* найкоротших шляхах (в метрах).
    
    @param G (nx.Graph): Робочий граф.
    @return (list): Відсортований список пар (node_id, centrality_score).
    """
    G_weighted = G.copy()
    
    # Призначаємо вагу 'weight' кожному ребру на основі 'lengthm'
    for u, v, data in G_weighted.edges(data=True):
        length_str = data.get('lengthm')
        try:
            # Конвертуємо довжину (рядок) у число
            data['weight'] = float(length_str)
        except (ValueError, TypeError, AttributeError):
            # Якщо даних немає або вони пошкоджені, ставимо вагу за замовчуванням
            data['weight'] = 1.0
            
    print("  ...рахую зважену центральність (~30 сек)...")
    
    # Запускаємо той самий алгоритм, але вказуємо 'weight'
    centrality = nx.betweenness_centrality(G_weighted, k=1000, normalized=True, weight='weight')
    
    return sorted(centrality.items(), key=lambda item: item[1], reverse=True)

# --- 5. ДАНІ ДЛЯ ГІСТОГРАМИ ---

def get_histogram_data(G):
    """
    Отримує дані для побудови гістограми розподілу ступенів.
    
    @param G (nx.Graph): Робочий граф.
    @return (pd.DataFrame): DataFrame з колонками ['Ступінь', 'Кількість вузлів'].
    """
    print("  ...готую дані для гістограми...")
    
    # nx.degree_histogram() повертає список [0, 1436, 4000, ...], 
    # де індекс - це ступінь, а значення - кількість.
    hist_list = nx.degree_histogram(G)
    
    # Конвертуємо у DataFrame для зручної роботи в Plotly
    df = pd.DataFrame({'Ступінь': range(len(hist_list)), 'Кількість вузлів': hist_list})
    
    # Видаляємо ступінь 0, оскільки він не має сенсу (ізольовані вузли ми видалили)
    df = df[df['Ступінь'] > 0] 
    return df

# --- 6. АНАЛІЗ: СТІЙКІСТЬ (РОЗРАХУНОК) ---

def calculate_robustness(G, nodes_to_attack):
    """
    Симулює цілеспрямовану атаку на мережу, послідовно видаляючи
    вузли зі списку 'nodes_to_attack'.
    На кожному кроці розраховує розмір найбільшого зв'язного компонента.
    
    @param G (nx.Graph): Робочий граф.
    @param nodes_to_attack (list): Відсортований список ID вузлів для атаки.
    @return (pd.DataFrame): DataFrame з кроками атаки та % "живої" мережі.
    """
    sizes = []
    # ОБОВ'ЯЗКОВО копіюємо граф, щоб не пошкодити оригінал (G_main)
    G_copy = G.copy() 
    initial_size = float(G_copy.number_of_nodes())
    sizes.append(1.0) # Крок 0: 0 видалено, 100% мережі
    
    total = len(nodes_to_attack)
    for i, node in enumerate(nodes_to_attack):
        if i % 10 == 0: 
            print(f"    ...прогрес стійкості: {i}/{total}", end='\r')
        
        # Вузол може бути вже видалений, якщо він "відвалився"
        # разом з іншим компонентом.
        if node not in G_copy:
            if sizes: sizes.append(sizes[-1]) # Дублюємо попередній результат
            continue
            
        G_copy.remove_node(node)
        
        if G_copy.number_of_nodes() == 0: 
            sizes.append(0.0) # Мережа повністю знищена
            continue
        
        # Знаходимо найбільший компонент ПІСЛЯ атаки
        largest_comp_nodes = max(nx.connected_components(G_copy), key=len)
        
        # Записуємо % живої мережі від початкового розміру
        sizes.append(len(largest_comp_nodes) / initial_size)
        
    print(f"    ...прогрес стійкості: {total}/{total} - Завершено.")
    
    # Конвертуємо у DataFrame для зручної роботи в Plotly
    df = pd.DataFrame({'Крок атаки': range(len(sizes)), 'Розмір мережі (%)': [s * 100 for s in sizes]})
    return df

# --- 7. ДАНІ ДЛЯ ГЕО-МАПИ (З НАПРУГОЮ) ---

def get_voltage_data_for_nodes(G):
    """
    Аналізує *всі ребра* графа, щоб визначити *максимальну напругу*
    для *кожного вузла*. Потім класифікує вузли за категоріями.
    Це "важка" операція, що виконується один раз при запуску.
    
    @param G (nx.Graph): Робочий граф.
    @return (pd.DataFrame): DataFrame з колонками [lat, lon, text, category, id].
    """
    print("  ...аналізую напругу для 9418 вузлів...")
    
    # 1. Проходимо по ребрам і знаходимо макс. напругу для вузлів
    node_voltages = defaultdict(int)
    for u, v, data in G.edges(data=True):
        voltage = _parse_voltage(data.get('voltage'))
        # Оновлюємо макс. напругу для ОБОХ вузлів на ребрі
        if voltage > node_voltages[u]: node_voltages[u] = voltage
        if voltage > node_voltages[v]: node_voltages[v] = voltage
    
    # 2. Проходимо по вузлам, витягуємо гео-дані та класифікуємо
    node_data = {'lat': [], 'lon': [], 'text': [], 'category': [], 'id': []}
    for node, data in G.nodes(data=True):
        lon_str = data.get('lon'); lat_str = data.get('lat')
        
        # Пропускаємо вузли без координат
        if not (lon_str and lat_str): continue
        try: 
            lat = float(lat_str); lon = float(lon_str)
        except (ValueError, TypeError): 
            continue
            
        max_v = node_voltages[node]
        
        # 3. Класифікуємо
        if max_v >= 380000: category = "380кВ+"
        elif max_v >= 220000: category = "220кВ"
        elif max_v >= 110000: category = "110кВ"
        else: category = "Інше (<110кВ)"
        
        # 4. Збираємо дані для DataFrame
        node_data['lat'].append(lat)
        node_data['lon'].append(lon)
        # Готуємо підказку для Plotly
        node_data['text'].append(f"ID: {node}<br>Max V: {max_v/1000:.0f}кВ<br>Lat: {lat:.4f}<br>Lon: {lon:.4f}")
        node_data['category'].append(category)
        node_data['id'].append(node) # Зберігаємо "чистий" ID для Callback
        
    return pd.DataFrame(node_data)

# --- 8. АНАЛІЗ: ВУЗЬКІ МІСЦЯ (MIN-CUT) ---

def get_bottleneck_analysis(G, source_node, sink_node):
    """
    Розраховує "вузьке місце" (Minimum Cut) між двома вузлами (source, sink).
    Використовує алгоритм Max-Flow / Min-Cut.
    
    @param G (nx.Graph): Робочий граф.
    @param source_node (str): ID вузла-джерела.
    @param sink_node (str): ID вузла-споживача.
    @return (dict, pd.DataFrame): 
        1. stats: Словник з KPI (кількість ліній, мін. напруга).
        2. df: DataFrame з деталями про ЛЕП у розрізі.
    """
    print(f"  ...рахую вузьке місце: {source_node} -> {sink_node}...")
    G_capacity = G.copy()
    
    # Призначаємо "пропускну здатність" (capacity) кожному ребру
    for u, v, data in G_capacity.edges(data=True):
        length_str = data.get('lengthm')
        try:
            length = float(length_str)
            if length == 0: 
                data['capacity'] = 1.0 # Уникаємо ділення на нуль
            else: 
                # Припускаємо, що пропускна здатність ~ 1 / Довжина
                # (коротші лінії = кращі)
                data['capacity'] = 1.0 / length 
        except (ValueError, TypeError, AttributeError):
            data['capacity'] = 1.0 # Стандартна capacity
            
    # 1. Головний розрахунок (Max-Flow / Min-Cut)
    cut_value, partition = nx_flow.minimum_cut(G_capacity, source_node, sink_node, capacity='capacity')
    
    reachable, non_reachable = partition
    
    # 2. Знаходимо ребра, які перетинають цей розріз
    bottleneck_edges = nx.edge_boundary(G_capacity, reachable, non_reachable)
    
    # 3. Збираємо статистику для KPI-карток
    bottleneck_data = []
    min_voltage = float('inf')
    
    for u, v in bottleneck_edges:
        edge_data = G_capacity.edges[u, v]
        voltage_str = edge_data.get('voltage', '0')
        voltage_num = _parse_voltage(voltage_str)
        
        # Шукаємо "найслабшу ланку" (найнижчу напругу в розрізі)
        if voltage_num > 0 and voltage_num < min_voltage:
            min_voltage = voltage_num
            
        bottleneck_data.append((f"{u} - {v}", voltage_str, f"{float(edge_data.get('lengthm', 0)):.1f} м"))
        
    if min_voltage == float('inf'): 
        min_voltage = 0
        
    df = pd.DataFrame(bottleneck_data, columns=["ЛЕП (Від - До)", "Напруга (V)", "Довжина (м)"])
    
    # Готуємо фінальний словник з KPI
    stats = {
        'cut_value_str': f"{cut_value:,.6f}",
        'line_count': len(df),
        'min_voltage_str': f"{min_voltage/1000:.0f} кВ" if min_voltage > 0 else "N/A"
    }
    
    return stats, df

# --- 9. АНАЛІЗ: СПІЛЬНОТИ ---

def get_communities_analysis(G):
    """
    Виконує кластеризацію мережі (пошук спільнот) за допомогою
    алгоритму Louvain.
    
    @param G (nx.Graph): Робочий граф.
    @return (pd.DataFrame, int): 
        1. DataFrame з Топ-15 спільнотами.
        2. Загальна кількість знайдених спільнот.
    """
    print("  ...рахую спільноти...")
    
    # Алгоритм Louvain - швидкий та ефективний для великих графів
    communities_sets = nx_comm.louvain_communities(G, seed=42)
    communities_list = sorted(communities_sets, key=len, reverse=True)
    
    # Готуємо дані для таблиці (лише Топ-15)
    community_data = [(f"Спільнота #{i+1}", f"{len(community)} вузлів") for i, community in enumerate(communities_list[:15])]
    
    return pd.DataFrame(community_data, columns=["Назва спільноти", "Розмір"]), len(communities_list)

# --- 10. АНАЛІЗ: СКЛАД ХАБІВ ---

def get_hubs_voltage_composition(G, top_10_hubs_list):
    """
    Аналізує склад ЛЕП (за напругою) для Топ-10 вузлів-хабів.
    
    @param G (nx.Graph): Робочий граф.
    @param top_10_hubs_list (list): Список пар (node_id, degree) з Топ-10.
    @return (pd.DataFrame): DataFrame, готовий для stacked bar chart в Plotly.
    """
    print("  ...аналізую склад Топ-10 Хабів...")
    hub_composition_data = []
    
    for hub_id, degree in top_10_hubs_list:
        # 1. Рахуємо лінії різної напруги для одного хаба
        counts = {"380кВ+": 0, "220кВ": 0, "110кВ": 0, "Інше": 0}
        
        for neighbor in G.neighbors(hub_id):
            edge_data = G.edges[hub_id, neighbor]
            max_v = _parse_voltage(edge_data.get('voltage'))
            
            # 2. Класифікуємо кожну ЛЕП
            if max_v >= 380000: counts["380кВ+"] += 1
            elif max_v >= 220000: counts["220кВ"] += 1
            elif max_v >= 110000: counts["110кВ"] += 1
            else: counts["Інше"] += 1
        
        # 3. Форматуємо дані для "stacked bar chart"
        for category, count in counts.items():
            if count > 0:
                hub_composition_data.append({
                    'hub_id': f"#{top_10_hubs_list.index((hub_id, degree))+1}: {hub_id} ({degree} ЛЕП)",
                    'Категорія напруги': category,
                    'Кількість ЛЕП': count
                })
                
    return pd.DataFrame(hub_composition_data)
