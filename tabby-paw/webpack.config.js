const path = require('path')

module.exports = {
  target: 'node',
  entry: './src/index.ts',
  devtool: 'source-map',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'index.js',
    libraryTarget: 'commonjs2',
  },
  resolve: {
    extensions: ['.ts', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: { loader: 'ts-loader', options: { configFile: 'tsconfig.json' } },
        exclude: /node_modules/,
      },
    ],
  },
  externals: [
    '@angular/core',
    '@angular/common',
    '@angular/forms',
    '@angular/platform-browser',
    'rxjs',
    'rxjs/operators',
    'tabby-core',
    'tabby-terminal',
    'tabby-settings',
    'electron',
    '@electron/remote',
    'fs',
    'path',
    'os',
  ],
}
