// Generic HTML -> PDF renderer used by the jsonresume-pdf skill.
// Usage: node html_to_pdf.js <input.html> <output.pdf>
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const [, , inputArg, outputArg] = process.argv;
if (!inputArg || !outputArg) {
  console.error('Usage: node html_to_pdf.js <input.html> <output.pdf>');
  process.exit(1);
}

const htmlPath = path.resolve(process.cwd(), inputArg);
const outPath = path.resolve(process.cwd(), outputArg);

if (!fs.existsSync(htmlPath)) {
  console.error('Input HTML not found:', htmlPath);
  process.exit(1);
}

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto('file://' + htmlPath, { waitUntil: 'networkidle0' });
  await page.pdf({
    path: outPath,
    format: 'A4',
    printBackground: true,
    margin: { top: '15mm', bottom: '15mm', left: '0', right: '0' },
  });
  await browser.close();
  console.log('PDF written to', outPath);
})();
