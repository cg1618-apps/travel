/** Every URL this app calls, in one map. */

export const endpoints = {
  backup: () => '/api/backup',
  packingLists: {
    index: () => '/api/packing-lists',
    detail: (id) => `/api/packing-lists/${id}`,
    items: (id) => `/api/packing-lists/${id}/items`,
    bulkCreate: (id) => `/api/packing-lists/${id}/items/bulk-create`,
    bulkDelete: (id) => `/api/packing-lists/${id}/items/bulk-delete`,
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
    routesOrder: () => '/api/transport-routes/order',
    route: (id) => `/api/transport-routes/${id}`,
    optionsOrder: (routeId) => `/api/transport-routes/${routeId}/order`,
    options: (routeId) => `/api/transport-routes/${routeId}/options`,
    notes: (routeId) => `/api/transport-routes/${routeId}/notes`,
    noteOrder: (routeId) => `/api/transport-routes/${routeId}/note-order`,
    note: (id) => `/api/transport-notes/${id}`,
    option: (id) => `/api/transport-options/${id}`,
    departures: (optionId) => `/api/transport-options/${optionId}/departures`,
    departure: (id) => `/api/transport-departures/${id}`,
  },
  notes: {
    index: () => '/api/notes',
    order: () => '/api/notes/order',
    detail: (id) => `/api/notes/${id}`,
  },
  trips: {
    index: () => '/api/trips',
    bulkDelete: () => '/api/trips/bulk-delete',
    detail: (id) => `/api/trips/${id}`,
    legs: (tripId) => `/api/trips/${tripId}/legs`,
    leg: (id) => `/api/trip-legs/${id}`,
    legBackups: (id) => `/api/trip-legs/${id}/backups`,
    promoteLeg: (id) => `/api/trip-legs/${id}/promote`,
  },
}
