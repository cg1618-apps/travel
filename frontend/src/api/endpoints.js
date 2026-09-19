/** Every URL this app calls, in one map. */

export const endpoints = {
  packingLists: {
    index: () => '/api/packing-lists',
    detail: (id) => `/api/packing-lists/${id}`,
    items: (id) => `/api/packing-lists/${id}/items`,
  },
  packingItems: {
    detail: (id) => `/api/packing-items/${id}`,
  },
  labelOptions: {
    index: (kind) => (kind ? `/api/label-options?kind=${kind}` : '/api/label-options'),
    detail: (id) => `/api/label-options/${id}`,
  },
}
