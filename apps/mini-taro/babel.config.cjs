module.exports = {
  plugins: [require.resolve('./config/babel-data-selector-markers.cjs')],
  presets: [
    ['taro', {
      framework: 'react',
      ts: true,
      compiler: 'webpack5',
    }],
  ],
}
