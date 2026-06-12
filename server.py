import json, math, random, itertools, heapq, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import networkx as nx

PORT = 8000
HERE = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────
# 1. BARTHELEMY SPATIAL SCALE-FREE MODEL
# ─────────────────────────────────────────────────────────────
def barthelemy_graph(n: int) -> nx.Graph:
    seed = random.randint(0, 999999)
    rng  = random.Random(seed)
    m    = max(2, int(math.log2(n)))

    G, pos = nx.Graph(), {}

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
        candidates.remove(new)
        degs  = dict(G.degree())
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
#    1) Vértices de grau ímpar
#    2) Matching mínimo entre eles (caminhos mínimos)
#    3) DUPLICAR arestas dos caminhos → multigrafo Euleriano
#    4) Fleury sobre o multigrafo
# ─────────────────────────────────────────────────────────────
def chinese_postman(G: nx.Graph):
    odd = [v for v, d in G.degree() if d % 2 == 1]

    pairs = list(itertools.combinations(odd, 2))
    sp_len, sp_path = {}, {}
    for u, v in pairs:
        length, path = nx.single_source_dijkstra(G, u, v, weight="weight")
        sp_len[(u, v)] = length
        sp_path[(u, v)] = path

    # matching guloso (menor caminho primeiro)
    matched, aug_paths = set(), []
    for u, v in sorted(pairs, key=lambda p: sp_len.get(p, 1e9)):
        if u not in matched and v not in matched:
            matched |= {u, v}
            aug_paths.append(sp_path[(u, v)])

    # multigrafo aumentado: DUPLICA cada aresta dos caminhos do matching
    MG = nx.MultiGraph()
    MG.add_nodes_from(G.nodes())
    for u, v, d in G.edges(data=True):
        MG.add_edge(u, v, weight=d["weight"])

    aug_display = []
    for path in aug_paths:
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            w = G[a][b]["weight"]
            MG.add_edge(a, b, weight=w)            # ← duplicação real
            aug_display.append((a, b, w))

    # sanidade: todo vértice do multigrafo deve ter grau PAR
    degrees_after = dict(MG.degree())
    assert all(d % 2 == 0 for d in degrees_after.values()), \
        "Erro: multigrafo aumentado não é Euleriano"

    circuit, cost = fleury(MG)
    return circuit, aug_display, cost, degrees_after


def fleury(MG: nx.MultiGraph):
    """
    Algoritmo de Fleury corrigido:
      - só atravessa ponte se não houver alternativa;
      - aresta paralela nunca é ponte;
      - teste de conexidade ignora vértices isolados (grau 0);
      - custo somado sobre a aresta exata removida (correto em multigrafo).
    """
    GC = nx.MultiGraph(MG)
    cur = next(iter(GC.nodes()))
    circuit, cost = [cur], 0

    def is_bridge(u, v):
        if GC.number_of_edges(u, v) > 1:
            return False                       # paralela nunca é ponte
        key = next(iter(GC[u][v]))
        w = GC[u][v][key]["weight"]
        GC.remove_edge(u, v, key=key)
        ok = u in GC and v in GC and nx.has_path(GC, u, v)
        GC.add_edge(u, v, key=key, weight=w)
        return not ok

    while GC.number_of_edges() > 0:
        nbrs = list(GC.neighbors(cur))
        if not nbrs:
            break
        if len(nbrs) == 1:
            nxt = nbrs[0]
        else:
            nxt = next((c for c in nbrs if not is_bridge(cur, c)), nbrs[0])

        key = next(iter(GC[cur][nxt]))
        cost += GC[cur][nxt][key]["weight"]
        GC.remove_edge(cur, nxt, key=key)
        if GC.degree(cur) == 0:
            GC.remove_node(cur)                # isolados não atrapalham has_path
        circuit.append(nxt)
        cur = nxt

    return circuit, cost


# ─────────────────────────────────────────────────────────────
# 3. MST — KRUSKAL e PRIM (implementações próprias,
#    registrando a ORDEM dos passos para animação)
# ─────────────────────────────────────────────────────────────
def mst_kruskal(G):
    parent = {v: v for v in G.nodes()}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    steps, edges, total = [], [], 0
    for u, v, d in sorted(G.edges(data=True), key=lambda e: e[2]["weight"]):
        w = d["weight"]
        ru, rv = find(u), find(v)
        accepted = ru != rv
        steps.append({"u": int(u), "v": int(v), "w": int(w), "accepted": accepted})
        if accepted:
            parent[ru] = rv
            edges.append((u, v, w))
            total += w
            if len(edges) == G.number_of_nodes() - 1:
                break
    return edges, total, steps


def mst_prim(G):
    start = next(iter(G.nodes()))
    visited = {start}
    heap = [(d["weight"], start, v) for v, d in G[start].items()]
    heapq.heapify(heap)

    steps, edges, total = [], [], 0
    while heap and len(visited) < G.number_of_nodes():
        w, u, v = heapq.heappop(heap)
        if v in visited:
            continue
        visited.add(v)
        edges.append((u, v, w))
        steps.append({"u": int(u), "v": int(v), "w": int(w), "accepted": True})
        total += w
        for nxt, d in G[v].items():
            if nxt not in visited:
                heapq.heappush(heap, (d["weight"], v, nxt))
    return edges, total, steps


# ─────────────────────────────────────────────────────────────
# 4. COMPLEXIDADE
# ─────────────────────────────────────────────────────────────
def complexity(n, m):
    return {
        "Barthelemy (geração)": f"O(n·log n)  →  n={n}",
        "PCC matching":         f"O(n³)  →  pares ímpares",
        "Fleury":               f"O(E²)  →  E={m}",
        "Kruskal":              f"O(E·log E)  →  E={m}",
        "Prim":                 f"O(E·log V)  →  V={n}, E={m}"
    }


# ─────────────────────────────────────────────────────────────
# 5. PIPELINE COMPLETO → dict JSON
# ─────────────────────────────────────────────────────────────
def build(n: int) -> dict:
    G = barthelemy_graph(n)
    circuit, aug, pcc_cost, deg_after = chinese_postman(G)
    k_e, k_c, k_steps = mst_kruskal(G)
    p_e, p_c, p_steps = mst_prim(G)

    pos = nx.get_node_attributes(G, "pos")
    nn, m = G.number_of_nodes(), G.number_of_edges()

    nodes = [{"id": int(v), "x": float(pos[v][0]), "y": float(pos[v][1]),
              "degree": int(G.degree(v)),
              "degree_pcc": int(deg_after[v])}
             for v in G.nodes()]

    edges = [{"source": int(u), "target": int(v), "weight": int(d["weight"])}
             for u, v, d in G.edges(data=True)]

    ids = sorted(G.nodes())
    adj = [[int(G[u][v]["weight"]) if G.has_edge(u, v) else 0 for v in ids] for u in ids]
    orig_cost = sum(d["weight"] for _, _, d in G.edges(data=True))

    return {
        "seed": int(G.graph["seed"]),
        "n": nn, "m": m,
        "nodes": nodes, "edges": edges,
        "node_ids": [int(i) for i in ids],
        "adjacency_matrix": adj,
        "pcc": {
            "circuit": [int(v) for v in circuit],
            "augmented_edges": [[int(u), int(v), int(w)] for u, v, w in aug],
            "total_cost": float(pcc_cost),
            "original_cost": float(orig_cost),
            "overhead_pct": round((pcc_cost - orig_cost) / orig_cost * 100, 2)
        },
        "kruskal": {"edges": [[int(u), int(v), int(w)] for u, v, w in k_e],
                    "total_cost": float(k_c), "steps": k_steps},
        "prim":    {"edges": [[int(u), int(v), int(w)] for u, v, w in p_e],
                    "total_cost": float(p_c), "steps": p_steps},
        "complexity": complexity(nn, m)
    }


# ─────────────────────────────────────────────────────────────
# 6. SERVIDOR HTTP
#    GET /                → index.html
#    GET /generate?n=30   → JSON do grafo gerado na hora
# ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)

        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return

        if url.path == "/generate":
            try:
                n = int(parse_qs(url.query).get("n", ["20"])[0])
                if not (4 <= n <= 500):
                    raise ValueError("n deve estar entre 4 e 500")
                data = build(n)
                self._send(200, json.dumps(data).encode(), "application/json")
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}).encode(),
                           "application/json")
            return

        self._send(404, b'{"error":"not found"}', "application/json")

    def log_message(self, fmt, *args):
        print("  [http]", fmt % args)


if __name__ == "__main__":
    print(f"Servidor rodando em  http://localhost:{PORT}")
    print("Abra esse endereço no navegador, digite n e clique em 'Gerar Grafo'.")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
