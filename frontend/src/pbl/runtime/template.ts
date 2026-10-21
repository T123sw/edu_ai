import index from './index.js?raw';
import runner from './runner.js?raw';
import workerSource from './worker-source.js?raw';
import styles from './styles.css?raw';
export const runtimeFiles = {
  '/src/index.js': index,
  '/src/runner.js': runner,
  '/src/worker-source.js': workerSource,
  '/src/styles.css': styles,
  '/index.html': '<!doctype html><html><head><meta charset="UTF-8"></head><body><div id="app"></div><script src="/src/index.js"></script></body></html>',
  '/package.json': JSON.stringify({name:'edu-pbl-runtime',version:'1.0.0',main:'/src/index.js',dependencies:{}},null,2),
};
