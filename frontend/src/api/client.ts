import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000",
  timeout: 60000,
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err?.response?.data?.detail ||
      err?.message ||
      "网络错误，请稍后重试";
    return Promise.reject(new Error(msg));
  }
);

export default client;