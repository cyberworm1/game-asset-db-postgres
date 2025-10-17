import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  withCredentials: true
});

apiClient.interceptors.request.use((config) => {
  // TODO: inject OAuth2 access token once auth flow is wired
  return config;
});

export default apiClient;
