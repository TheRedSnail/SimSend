const countOf = (graph, countKey, listKey) => {
  if (!graph) return -1
  return graph[countKey] ?? graph[listKey]?.length ?? 0
}

/**
 * Whether freshly fetched graph data differs from what is displayed.
 *
 * GraphPanel deep-watches its data and rebuilds the force layout from scratch
 * on every change, wiping the user's zoom/pan/selection, so periodic refreshes
 * should only reassign when the graph actually grew or shrank.
 */
export function graphChanged(prev, next) {
  if (!next) return false
  return countOf(prev, 'node_count', 'nodes') !== countOf(next, 'node_count', 'nodes') ||
    countOf(prev, 'edge_count', 'edges') !== countOf(next, 'edge_count', 'edges')
}
