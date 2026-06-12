"""
generate_graph.py
Barthelemy Spatial Scale-Free Graph Generator
CLI:    python generate_graph.py --n 30
API:    from generate_graph import generate_all; data = generate_all(30)
"""

import argparse
import heapq
import itertools
import json
import math
import random

import networkx as nx


# ─────────────────────────────────────────────────────────────
# 1. BARTHELEMY SPATIAL SCALE-FREE MODEL
# ─────────────────────────────────────────────────────────────
def barthelemy_graph(n: int) -> nx.Graph:
    seed = random.randint(0, 999999)
    rng = random.Random(seed)
    m = max(2, int(math.log2(n)))

    G = nx.Graph()
    pos = {}

    for i in range(m + 1):
        pos[i] = (rng.random(), rng.random())
        G.add_node(i)
    for u in range(m + 1):
        for v in range(u + 1, m + 1):
            G.add_edge(u, v, weight=rng.randint(1, 20))

    for new in range(m + 1, n):
        x, y = rng.random(), rng.random()
        pos[new] = (x, y)
        G.add_node(new)

        candidates = list(G.nodes())
        degs = dict(G.degree())
        probs = []
        for c in candidates:
            cx, cy = pos[c]
            d = math.hypot(x - cx, y - cy) + 1e-9
            probs.append(degs[c] / d)
        total = sum(probs)
        probs = [p / total for p in probs]

        targets, safety = set(), 0
        while len(targets) < min(m, len(candidates)) and safety < 1000:
            safety += 1
            r, cum = rng.random(), 0.0
            for idx, p in enumerate(probs):
                cum += p
                if r <= cum:
                    targets.add(candidates[idx])
                    break
        for t in targets:
            if not G.has_edge(new, t):
                G.add_edge(new, t, weight=rng.randint(1, 20))

    comps = list(nx.connected_components(G))
    while len(comps) > 1:
        u = rng.choice(list(comps[0]))
        v = rng.choice(list(comps[1]))
        G.add_edge(u, v, weight=rng.randint(1, 20))
        comps = list(nx.connected_components(G))

    nx.set_node_attributes(G, pos, "pos")
    G.graph["seed"] = seed
    return G


# ─────────────────────────────────────────────────────────────
# 2. PCC — PROBLEMA DO CARTEIRO CHINÊS
# ─────────────────────────────────────────────────────────────
def chinese_postman(G: nx.Graph):
    """
    Algoritmo do Carteiro Chinês (Route Inspection) para grafos não-dirigidos.

    Etapas:
      1. Identificar todos os vértices de grau ímpar.
      2. Calcular caminhos mínimos (Dijkstra) entre todos os pares de vértices ímpares.
      3. Encontrar emparelhamento perfeito de peso mínimo (algoritmo de Blossom).
      4. Duplicar as arestas dos caminhos mínimos do emparelhamento, tornando
         todos os graus pares — condição necessária para circuito Euleriano.
      5. Encontrar circuito Euleriano no multigrafo aumentado (Hierholzer O(E)).

    Bugs corrigidos vs. implementação anterior:
      - Fleury substituído por Hierholzer (ver docstring de hierholzer).
      - Custo calculado como soma de TODAS as arestas do MultiGraph aumentado,
        não por indexação [0] que sempre lê a mesma aresta paralela.
      - Lookup do caminho mínimo robusto a qualquer ordem de (u, v) no matching.
    """
    # --- Etapa 1: vértices de grau ímpar ---
    odd = [v for v, d in G.degree() if d % 2 == 1]

    # --- Etapa 2: distâncias mínimas entre todos os pares de vértices ímpares ---
    pairs = list(itertools.combinations(odd, 2))
    sp_len: dict = {}
    sp_path: dict = {}
    for u, v in pairs:
        length, path = nx.single_source_dijkstra(G, u, v, weight="weight")
        sp_len[(u, v)] = length
        sp_path[(u, v)] = path

    # --- Etapa 3: emparelhamento perfeito de peso mínimo ---
    # H é o grafo completo sobre os vértices ímpares com pesos = dist. mínima
    H = nx.Graph()
    H.add_nodes_from(odd)
    for u, v in pairs:
        H.add_edge(u, v, weight=sp_len[(u, v)])

    # min_weight_matching usa o algoritmo de Blossom (via max_weight_matching com
    # maxcardinality=True e pesos negados) — garante emparelhamento PERFEITO de
    # peso mínimo, pois |odd| é sempre par (lema do aperto de mãos).
    matching = nx.min_weight_matching(H, weight="weight")

    # --- Etapa 4: duplicar arestas ao longo dos caminhos do emparelhamento ---
    MG = nx.MultiGraph(G)
    aug_display = []

    for u, v in matching:
        # O matching pode retornar (u,v) ou (v,u); sp_path foi preenchido via
        # combinations, então a chave existe em apenas uma das ordens.
        key = (u, v) if (u, v) in sp_path else (v, u)
        path = sp_path[key]
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            w = G[a][b]["weight"]
            MG.add_edge(a, b, weight=w)
            aug_display.append((a, b, w))

    # --- Etapa 5: circuito Euleriano via Hierholzer ---
    circuit = hierholzer(MG)

    # Custo total = soma de TODAS as arestas do multigrafo aumentado.
    # Como o circuito Euleriano percorre cada aresta exatamente uma vez,
    # isso equivale ao custo do percurso sem precisar indexar o circuito.
    cost = sum(d["weight"] for _, _, d in MG.edges(data=True))

    return circuit, aug_display, cost


def hierholzer(MG: nx.MultiGraph) -> list:
    """
    Algoritmo de Hierholzer — encontra circuito Euleriano em O(E).

    Pré-condição: MG é conexo e todos os vértices têm grau par.
    Ambas as condições são garantidas após a etapa de aumentação do PCC.

    Por que Fleury estava errado:
      - Fleury exige detectar pontes via is_connected a cada passo.
      - Em um MultiGraph, vértices já esgotados ficam isolados (grau 0),
        fazendo is_connected retornar False mesmo quando o grafo de arestas
        restantes é conexo. Isso impedia qualquer movimento "válido" e forçava
        sempre o fallback, que ignora pontes por completo.
      - Além disso, o break precoce deixava o circuito incompleto.

    Hierholzer (iterativo):
      - Mantém uma pilha de vértices a explorar.
      - Ao encontrar um vértice sem mais arestas, retrocede adicionando-o
        ao circuito — inserindo automaticamente sub-ciclos onde necessário.
      - Não requer verificação de ponte: a estrutura da pilha garante
        que todas as arestas sejam percorridas exatamente uma vez.
    """
    G = MG.copy()
    start = next(iter(G.nodes()))

    stack = [start]
    circuit = []

    while stack:
        v = stack[-1]
        if G.degree(v) > 0:
            # Seguir qualquer aresta ainda disponível (remove uma instância)
            u = next(iter(G.neighbors(v)))
            stack.append(u)
            G.remove_edge(v, u)
        else:
            # Vértice esgotado: registra no circuito e retrocede na pilha
            circuit.append(v)
            stack.pop()

    # O circuito é construído de trás para frente; revertemos ao final.
    return circuit[::-1]


# ─────────────────────────────────────────────────────────────
# 3. MST — KRUSKAL e PRIM com steps ordenados para animação
# ─────────────────────────────────────────────────────────────
def mst_kruskal_steps(G):
    """Retorna arestas na ordem em que Kruskal as aceita (union-find)."""
    sorted_edges = sorted(G.edges(data=True), key=lambda e: e[2]["weight"])
    parent = {v: v for v in G.nodes()}
    rank = {v: 0 for v in G.nodes()}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return False
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1
        return True

    steps = []
    for u, v, d in sorted_edges:
        if union(u, v):
            steps.append([int(u), int(v), int(d["weight"])])

    total = sum(s[2] for s in steps)
    return steps, float(total)


def mst_prim_steps(G):
    """Retorna arestas na ordem em que Prim as aceita."""
    if not G.nodes():
        return [], 0.0

    start = min(G.nodes())
    visited = {start}
    heap = []
    steps = []

    for nb in G.neighbors(start):
        heapq.heappush(heap, (G[start][nb]["weight"], int(start), int(nb)))

    while heap and len(visited) < G.number_of_nodes():
        w, u, v = heapq.heappop(heap)
        if v in visited:
            continue
        visited.add(v)
        steps.append([int(u), int(v), int(w)])
        for nb in G.neighbors(v):
            if nb not in visited:
                heapq.heappush(heap, (G[v][nb]["weight"], int(v), int(nb)))

    total = sum(s[2] for s in steps)
    return steps, float(total)


# ─────────────────────────────────────────────────────────────
# 4. COMPLEXIDADE
# ─────────────────────────────────────────────────────────────
def complexity(n, m):
    return {
        "Barthelemy (geração)": f"O(n · log n)  →  n={n}",
        "PCC matching": f"O(n³)  →  pares ímpares",
        "Hierholzer": f"O(E)  →  E={m}",
        "Kruskal": f"O(E · log E)  →  E={m}",
        "Prim": f"O(E · log V)  →  V={n}, E={m}",
    }


# ─────────────────────────────────────────────────────────────
# 5. SERIALIZAÇÃO
# ─────────────────────────────────────────────────────────────
def serialize(G, circuit, aug_display, pcc_cost, k_steps, k_cost, p_steps, p_cost):
    pos = nx.get_node_attributes(G, "pos")
    n, m = G.number_of_nodes(), G.number_of_edges()

    nodes = [
        {
            "id": int(v),
            "x": float(pos[v][0]),
            "y": float(pos[v][1]),
            "degree": int(G.degree(v)),
        }
        for v in G.nodes()
    ]

    edges = [
        {"source": int(u), "target": int(v), "weight": int(d["weight"])}
        for u, v, d in G.edges(data=True)
    ]

    ids = sorted(G.nodes())
    adj_matrix = []
    for u in ids:
        row = []
        for v in ids:
            row.append(int(G[u][v]["weight"]) if G.has_edge(u, v) else 0)
        adj_matrix.append(row)

    orig_cost = sum(d["weight"] for _, _, d in G.edges(data=True))

    return {
        "seed": int(G.graph.get("seed", 0)),
        "n": n,
        "m": m,
        "nodes": nodes,
        "edges": edges,
        "node_ids": [int(i) for i in ids],
        "adjacency_matrix": adj_matrix,
        "pcc": {
            "circuit": [int(v) for v in circuit],
            "augmented_edges": [[int(u), int(v), int(w)] for u, v, w in aug_display],
            "total_cost": float(pcc_cost),
            "original_cost": float(orig_cost),
            "overhead_pct": round((pcc_cost - orig_cost) / orig_cost * 100, 2),
        },
        "kruskal": {
            "steps": k_steps,
            "edges": k_steps,  # alias — mesmo dado
            "total_cost": k_cost,
        },
        "prim": {"steps": p_steps, "edges": p_steps, "total_cost": p_cost},
        "complexity": complexity(n, m),
    }


# ─────────────────────────────────────────────────────────────
# 6. API PÚBLICA
# ─────────────────────────────────────────────────────────────
def generate_all(n: int) -> dict:
    """Gera grafo + PCC + MST. Retorna dict pronto para JSON."""
    G = barthelemy_graph(n)
    circuit, aug, pcc_cost = chinese_postman(G)
    k_steps, k_cost = mst_kruskal_steps(G)
    p_steps, p_cost = mst_prim_steps(G)
    return serialize(G, circuit, aug, pcc_cost, k_steps, k_cost, p_steps, p_cost)


# ─────────────────────────────────────────────────────────────
# 7. CLI
# ─────────────────────────────────────────────────────────────
def main():
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", type=str, default="graph_data.json")
    args = ap.parse_args()
    if args.n < 4:
        print("Erro: n deve ser >= 4")
        return

    print(f"[1/5] Gerando grafo Barthelemy  n={args.n}...")
    data = generate_all(args.n)
    print(f"      {data['n']} nós · {data['m']} arestas · seed={data['seed']}")

    print("[2/5] PCC ok")
    print(f"      custo={data['pcc']['total_cost']}")
    print(f"[3/5] Kruskal  custo={data['kruskal']['total_cost']}")
    print(f"[4/5] Prim     custo={data['prim']['total_cost']}")
    print("[5/5] Exportando JSON...")

    with open(args.out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"      Salvo em {args.out}  ({round(os.path.getsize(args.out)/1024,1)} KB)")


if __name__ == "__main__":
    main()