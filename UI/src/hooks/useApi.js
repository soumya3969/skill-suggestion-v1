import { useState, useCallback } from 'react';

/**
 * Custom hook for API calls with loading and error states
 * 
 * @param {Function} apiFunction - API function to call
 * @returns {Object} - { data, loading, error, execute, reset }
 */
export function useApi(apiFunction) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await apiFunction(...args);
      setData(result);
      return result;
    } catch (err) {
      const errorMessage = err.message || 'An unexpected error occurred';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFunction]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
}

/**
 * Custom hook for polling API at regular intervals
 * 
 * @param {Function} apiFunction - API function to call
 * @param {number} interval - Polling interval in milliseconds
 * @param {boolean} enabled - Whether polling is enabled
 */
export function usePollingApi(apiFunction, interval = 5000, enabled = true) {
  const { data, loading, error, execute, reset } = useApi(apiFunction);

  // Set up polling
  useState(() => {
    if (!enabled) return;

    // Initial fetch
    execute();

    // Set up interval
    const pollId = setInterval(() => {
      execute();
    }, interval);

    return () => clearInterval(pollId);
  }, [enabled, interval]);

  return { data, loading, error, refresh: execute, reset };
}

export default useApi;
