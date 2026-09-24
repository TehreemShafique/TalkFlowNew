"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState("dark"); // "dark" | "light"

  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("talkflow_theme");
      if (savedTheme === "light") {
        setThemeState("light");
        document.documentElement.classList.remove("dark");
      } else {
        setThemeState("dark");
        document.documentElement.classList.add("dark");
      }
    }
  }, []);

  const updateThemeDOM = (nextTheme) => {
    if (typeof window !== "undefined") {
      const root = document.documentElement;
      // Temporarily disable CSS transitions globally to prevent component-by-component color flicker
      root.classList.add("[&_*]:!transition-none");

      if (nextTheme === "light") {
        root.classList.remove("dark");
        localStorage.setItem("talkflow_theme", "light");
      } else {
        root.classList.add("dark");
        localStorage.setItem("talkflow_theme", "dark");
      }

      // Force browser layout reflow before re-enabling transitions
      window.getComputedStyle(root).opacity;

      setTimeout(() => {
        root.classList.remove("[&_*]:!transition-none");
      }, 10);
    }
  };

  const toggleTheme = () => {
    setThemeState((prevTheme) => {
      const nextTheme = prevTheme === "light" ? "dark" : "light";
      updateThemeDOM(nextTheme);
      return nextTheme;
    });
  };

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    updateThemeDOM(newTheme);
  };

  const isDark = theme === "dark";

  return (
    <ThemeContext.Provider value={{ theme, isDark, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
