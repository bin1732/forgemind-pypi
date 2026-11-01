// Mock lucide-react — 所有 icon 组件返空 div
const React = require("react");
const MockIcon = (props) => React.createElement("span", props, "icon");
const handler = {
  get: (target, prop) => {
    if (prop === "__esModule") return true;
    if (prop === "default") return target;
    return MockIcon;
  },
};

const mockObj = new Proxy(MockIcon, handler);
module.exports = mockObj;
module.exports.default = mockObj;