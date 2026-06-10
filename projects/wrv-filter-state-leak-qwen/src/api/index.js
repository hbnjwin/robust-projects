/**
 * API stubs for the expert-database module.
 * Replace with real axios calls in production.
 */
export const EXPERT_DATABASE = {
  /**
   * @param {Object} params - { docType, keyword, current, pageSize, sortBy?, order? }
   * @returns {Promise<{ list: Array, total: number }>}
   */
  getDocumentList: async (params) => {
    console.log('[API stub] getDocumentList called with:', params)
    return { list: [], total: 0 }
  },
}
