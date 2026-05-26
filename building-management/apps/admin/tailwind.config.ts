import type { Config } from 'tailwindcss';
import preset from '@bm/config/tailwind';

const config: Config = {
  presets: [preset as Config],
  content: ['./src/app/**/*.{ts,tsx}', './src/components/**/*.{ts,tsx}'],
};

export default config;
