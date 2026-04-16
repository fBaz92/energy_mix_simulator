/**
 * Axios HTTP client configured for the FastAPI backend.
 *
 * Base URL is relative (/api) because Vite's dev proxy forwards /api
 * requests to http://127.0.0.1:8000. In production, the backend should
 * serve the frontend static files (or use a reverse proxy).
 */
import axios from "axios";

export const api = axios.create({
  baseURL: "",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});
