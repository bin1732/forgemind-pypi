/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    "\\.(css|less|scss)$": "<rootDir>/__mocks__/styleMock.js",
    // Mock 第三方 UI 库,避免 jsdom 环境解析失败
    "^lightweight-charts$": "<rootDir>/__mocks__/lightweight-charts-mock.js",
    "^lucide-react$": "<rootDir>/__mocks__/lucide-react-mock.js",
  },
  testMatch: ["<rootDir>/components/__tests__/**/*.test.ts", "<rootDir>/components/__tests__/**/*.test.tsx"],
  transform: {
    "^.+\\.(ts|tsx)$": [
      "ts-jest",
      {
        tsconfig: {
          jsx: "react-jsx",
          esModuleInterop: true,
          allowSyntheticDefaultImports: true,
          target: "es2020",
          module: "commonjs",
        },
      },
    ],
  },
  testPathIgnorePatterns: ["/node_modules/", "/.next/", "/dist/"],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
};