export const fetchAPI = async (endpoint, options = {}) => {
  const token = localStorage.getItem('accessToken');
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  // We rely on the Nginx proxy to forward /api/ requests to the APIGateway
  const url = `/api${endpoint}`;

  // If there's a token and it's a GET request, we might need to append it as a query param
  // based on the previous PHP implementation (?access_token=...).
  // Alternatively, if the API supports it in headers, we'd add it to headers.
  // We'll append it to the URL just to match the PHP backend's behavior.
  
  let finalUrl = url;
  if (token) {
    const separator = finalUrl.includes('?') ? '&' : '?';
    finalUrl += `${separator}access_token=${token}`;
  }

  const response = await fetch(finalUrl, config);
  const text = await response.text();
  
  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    console.error("Non-JSON API Response:", text);
    throw new Error(`Server returned a non-JSON response (Status: ${response.status}). Check console for details.`);
  }
  
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      const error = new Error('Unauthorized');
      error.status = response.status;
      throw error;
    }
    throw new Error(data?.message || 'API request failed');
  }

  return data.data;
};

export const getGroups = async (userToken) => {
  return await fetchAPI(`/pub_sub/v1/view/groups/user/${userToken}/subscribed`);
};

export const getRootCatalogs = async (userToken) => {
  const allSubscribed = await fetchAPI(`/pubsub/${userToken}/catalogs/subscribed`);
  return allSubscribed; // Return raw data and handle mapping in the component
};

/**
 * Get contents (sub-catalogs and files) of a specific catalog
 * 
 * @param {string} userToken - The user's authentication token
 * @param {string} fatherToken - The parent catalog token
 * @returns {Promise<Object>} An object containing subCatalogs and files
 */
export const getCatalogContents = async (userToken, fatherToken) => {
  const [catalogsData, filesData] = await Promise.all([
    fetchAPI(`/pubsub/${userToken}/catalog/${fatherToken}/results`),
    fetchAPI(`/pubsub/${userToken}/catalog/${fatherToken}/list`)
  ]);

  return {
    catalogs: catalogsData || [],
    files: filesData || []
  };
};

export const getSystemHealth = async () => {
  return fetchAPI('/health');
};

export const forceReplication = async () => {
  return fetchAPI('/replicate', {
    method: 'POST'
  });
};
