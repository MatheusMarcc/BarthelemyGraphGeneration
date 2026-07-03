# Grafos Espaciais & Problema do Carteiro Chinês

Servidor HTTP em Python puro que gera um grafo espacial livre de escala (modelo de Barthelemy), resolve o **Problema do Carteiro Chinês (PCC)** sobre ele e calcula a **Árvore Geradora Mínima (MST)** por dois algoritmos diferentes (Kruskal e Prim), retornando tudo em JSON para visualização no navegador.

## ✨ Funcionalidades

- **Geração de grafo espacial** (`barthelemy_graph`): cria um grafo aleatório onde a probabilidade de conexão entre nós depende do grau do vizinho e da distância euclidiana entre eles (preferential attachment + proximidade espacial). Garante conectividade final unindo componentes isoladas.
- **Problema do Carteiro Chinês** (`chinese_postman`):
  1. Identifica vértices de grau ímpar.
  2. Calcula caminhos mínimos entre pares de vértices ímpares (Dijkstra).
  3. Faz um *matching* guloso (menor caminho primeiro) entre esses pares.
  4. Duplica as arestas dos caminhos do matching, transformando o grafo em um multigrafo Euleriano.
  5. Executa o **Algoritmo de Fleury** (com tratamento correto de pontes/arestas paralelas) para obter o circuito Euleriano final e seu custo total.
- **MST — Kruskal** (`mst_kruskal`): implementação própria com *union-find* (path compression), registrando cada passo (aresta aceita ou rejeitada) para fins de animação.
- **MST — Prim** (`mst_prim`): implementação própria com heap de prioridade, também registrando os passos.
- **Análise de complexidade** (`complexity`): retorna a notação Big-O aproximada de cada etapa do pipeline, já com os valores de `n`/`E` do grafo gerado.
- **API HTTP simples**, sem dependências além de `networkx`.

## 📦 Requisitos

- Python 3.8+
- [`networkx`](https://networkx.org/)

Instalação:

```bash
pip install networkx
```

## ▶️ Como executar

```bash
python server.py
```

O servidor sobe em:

```
http://localhost:8000
```

> ⚠️ O servidor tenta servir um arquivo `index.html` (na mesma pasta de `server.py`) na rota `/`. Esse arquivo **não está incluído neste pacote** — é necessário criar/adicionar seu próprio front-end para visualizar o grafo, ou consumir a rota `/generate` diretamente (veja abaixo).

## 🌐 Endpoints

### `GET /`
Serve o arquivo `index.html` (deve estar na mesma pasta do `server.py`).

### `GET /generate?n=<int>`
Gera um novo grafo aleatório com `n` nós (`4 ≤ n ≤ 500`) e executa todo o pipeline (Barthelemy → PCC → Kruskal → Prim).

**Exemplo:**
```bash
curl "http://localhost:8000/generate?n=30"
```

**Resposta (resumo dos campos):**

```jsonc
{
  "seed": 123456,
  "n": 30, "m": 57,
  "nodes": [{ "id": 0, "x": 0.42, "y": 0.71, "degree": 3, "degree_pcc": 4 }, ...],
  "edges": [{ "source": 0, "target": 5, "weight": 12 }, ...],
  "node_ids": [0, 1, 2, ...],
  "adjacency_matrix": [[0, 12, 0, ...], ...],
  "pcc": {
    "circuit": [0, 5, 3, ...],
    "augmented_edges": [[0, 5, 12], ...],
    "total_cost": 480.0,
    "original_cost": 410.0,
    "overhead_pct": 17.07
  },
  "kruskal": {
    "edges": [[0, 5, 12], ...],
    "total_cost": 210.0,
    "steps": [{ "u": 0, "v": 5, "w": 12, "accepted": true }, ...]
  },
  "prim": {
    "edges": [[0, 5, 12], ...],
    "total_cost": 210.0,
    "steps": [{ "u": 0, "v": 5, "w": 12, "accepted": true }, ...]
  },
  "complexity": {
    "Barthelemy (geração)": "O(n·log n)  →  n=30",
    "PCC matching": "O(n³)  →  pares ímpares",
    "Fleury": "O(E²)  →  E=57",
    "Kruskal": "O(E·log E)  →  E=57",
    "Prim": "O(E·log V)  →  V=30, E=57"
  }
}
```

Em caso de erro (ex.: `n` fora do intervalo permitido), a resposta tem status `400`:
```json
{ "error": "n deve estar entre 4 e 500" }
```

## 🧠 Estrutura do código

| Seção | Função(ões) | Descrição |
|---|---|---|
| 1 | `barthelemy_graph` | Geração do grafo espacial livre de escala |
| 2 | `chinese_postman`, `fleury` | Solução do Problema do Carteiro Chinês |
| 3 | `mst_kruskal`, `mst_prim` | Árvore Geradora Mínima (dois algoritmos) |
| 4 | `complexity` | Estimativas de complexidade computacional |
| 5 | `build` | Monta o dicionário/JSON final do pipeline completo |
| 6 | `Handler`, `ThreadingHTTPServer` | Servidor HTTP (rotas `/` e `/generate`) |

## 📝 Notas técnicas

- O peso de cada aresta é sorteado aleatoriamente entre 1 e 20.
- A semente aleatória (`seed`) usada em cada geração é retornada na resposta, permitindo reproduzir o mesmo grafo se necessário.
- O algoritmo de Fleury foi implementado com cuidado extra: nunca trata uma aresta paralela como ponte, e testa conectividade ignorando vértices já isolados — evitando o erro clássico de "ficar preso" em circuitos Eulerianos sobre multigrafos.
- CORS está liberado (`Access-Control-Allow-Origin: *`), então a API pode ser consumida por um front-end hospedado em outra origem/porta.

## 📄 Licença

Não especificada — adicione a licença de sua preferência.
