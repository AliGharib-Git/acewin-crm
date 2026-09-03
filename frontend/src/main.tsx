import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { LanguageProvider } from "./context/LanguageContext";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <LanguageProvider>
        <AuthProvider>
          <App />
          <Toaster
            position="top-left"
            toastOptions={{
              style: {
                background: "#0D151C",
                color: "#EAF3F0",
                fontFamily: "IBM Plex Sans, sans-serif",
                fontSize: "14px",
              },
              success: { iconTheme: { primary: "#14D9A6", secondary: "#EAF3F0" } },
              error: { iconTheme: { primary: "#F2555B", secondary: "#EAF3F0" } },
            }}
          />
        </AuthProvider>
        </LanguageProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
