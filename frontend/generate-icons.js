#!/usr/bin/env node
const sharp = require('sharp');
const fs = require('fs').promises;
const path = require('path');

async function generateIcons() {
  const svgPath = path.join(__dirname, 'public', 'icon.svg');
  const svgBuffer = await fs.readFile(svgPath);

  const sizes = [
    { size: 192, filename: 'icon-192x192.png' },
    { size: 512, filename: 'icon-512x512.png' },
  ];

  for (const { size, filename } of sizes) {
    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(path.join(__dirname, 'public', filename));
    console.log(`Generated ${filename}`);
  }

  console.log('All PWA icons generated successfully!');
}

generateIcons().catch(console.error);
