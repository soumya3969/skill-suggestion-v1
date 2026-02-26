import { useState, useMemo, useCallback } from 'react';

/**
 * Hook for server-side pagination state.
 * Tracks current page, page size, and total count from the API.
 *
 * @param {Object} options
 * @param {number} options.total - Total number of items (from API response)
 * @param {number} [options.initialPageSize=10] - Default page size
 * @param {number} [options.initialPage=1] - Initial page (1-based)
 * @returns Pagination state and helpers for UI
 */
export function usePagination({ total = 0, initialPageSize = 10, initialPage = 1 }) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const totalPages = useMemo(() => {
    if (total <= 0 || pageSize <= 0) return 0;
    return Math.ceil(total / pageSize);
  }, [total, pageSize]);

  const hasNextPage = page < totalPages;
  const hasPrevPage = page > 1;

  /** Start index (1-based) of current page for "Showing X–Y of Z" */
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  /** End index (1-based) of current page */
  const endItem = Math.min(page * pageSize, total);

  const goToNextPage = useCallback(() => {
    setPage((p) => Math.min(p + 1, totalPages));
  }, [totalPages]);

  const goToPrevPage = useCallback(() => {
    setPage((p) => Math.max(p - 1, 1));
  }, []);

  /** When page size changes, reset to page 1 so we don't land on an empty page */
  const handlePageSizeChange = useCallback((newSize) => {
    setPageSize(newSize);
    setPage(1);
  }, []);

  return {
    page,
    setPage,
    pageSize,
    setPageSize: handlePageSizeChange,
    total,
    totalPages,
    hasNextPage,
    hasPrevPage,
    startItem,
    endItem,
    goToNextPage,
    goToPrevPage,
  };
}
