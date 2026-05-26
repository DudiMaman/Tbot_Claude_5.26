/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  transpilePackages: ['@bm/shared', '@bm/config'],
  i18n: {
    locales: ['he', 'en'],
    defaultLocale: 'he',
  },
};
