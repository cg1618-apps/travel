/** Every URL this app calls, in one map. */

export const endpoints = {
  packingLists: {
    index: () => '/api/packing-lists',
    detail: (id) => `/api/packing-lists/${id}`,
    items: (id) => `/api/packing-lists/${id}/items`,
    bulkCreate: (id) => `/api/packing-lists/${id}/items/bulk-create`,
    order: (id) => `/api/packing-lists/${id}/order`,
    reset: (id) => `/api/packing-lists/${id}/reset`,
  },
  packingItems: {
    detail: (id) => `/api/packing-items/${id}`,
  },
  labelOptions: {
    index: (kind) => (kind ? `/api/label-options?kind=${kind}` : '/api/label-options'),
    detail: (id) => `/api/label-options/${id}`,
  },
  transport: {
    routes: () => '/api/transport-routes',
    route: (id) => `/api/transport-routes/${id}`,
    options: (routeId) => `/api/transport-routes/${routeId}/options`,
    option: (id) => `/api/transport-options/${id}`,
    departures: (optionId) => `/api/transport-options/${optionId}/departures`,
    departure: (id) => `/api/transport-departures/${id}`,
  },
  trips: {
    index: () => '/api/trips',
    bulkDelete: () => '/api/trips/bulk-delete',
    detail: (id) => `/api/trips/${id}`,
    legs: (tripId) => `/api/trips/${tripId}/legs`,
    leg: (id) => `/api/trip-legs/${id}`,
  },
}
