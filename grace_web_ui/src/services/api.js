import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_BASE_URL,
});

export const sendMessage = (message) => api.post('/chat', { message });
export const uploadImage = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/upload-image', formData);
};
export const fetchCatalog = () => api.get('/catalog');
export const fetchPayment = () => api.get('/payment');
export const updatePrompt = (prompt) => api.post('/prompt', { prompt });
