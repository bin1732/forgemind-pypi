/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Tauri 需要一个真正的静态站点目录。
  // 没有开 export 时,`next build` 只产出 .next 构建缓存(BUILD_ID / manifests / cache),
  // 而 tauri.conf.json 的 frontendDist 指向的正是 ../.next ——
  // 桌面端启动后没有可服务的 index.html,表现为白屏。
  // 开启 export 后产物在 out/,frontendDist 相应改为 ../out。
  output: "export",
  // 静态导出下不支持图片优化与 next/image 的运行时优化器
  images: { unoptimized: true },
  // 桌面端用 file:// 协议加载,需要相对路径
  trailingSlash: true,
};

module.exports = nextConfig;
