// The public build runs entirely in the browser with sample data. Build or run
// with VITE_BACKEND=1 to use the FastAPI backend instead (see README).
export const DEMO = import.meta.env.VITE_BACKEND !== '1'
