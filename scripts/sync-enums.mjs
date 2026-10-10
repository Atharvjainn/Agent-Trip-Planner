import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const enumsSourceDir = path.join(rootDir, 'packages', 'shared', 'enums');
const backendTargetDir = path.join(rootDir, 'backend', 'src', 'shared');
const frontendTargetDir = path.join(rootDir, 'frontend', 'app', 'lib', 'shared');

const targetDirs = [backendTargetDir, frontendTargetDir];

if (!fs.existsSync(enumsSourceDir)) {
  console.error(`Enums source directory not found: ${enumsSourceDir}`);
  process.exit(1);
}

for (const targetDir of targetDirs) {
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
}

const enumFiles = fs.readdirSync(enumsSourceDir).filter((file) => file.endsWith('.json'));

for (const file of enumFiles) {
  const sourcePath = path.join(enumsSourceDir, file);
  const content = fs.readFileSync(sourcePath, 'utf8');

  for (const targetDir of targetDirs) {
    const targetPath = path.join(targetDir, file);
    fs.writeFileSync(targetPath, content, 'utf8');
    console.log(`Copied ${file} -> ${path.relative(rootDir, targetPath)}`);
  }
}

console.log('Enum synchronization complete.');
