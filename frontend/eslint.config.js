// Solo la regla que evita el fallo "Rendered more hooks than during the
// previous render": ningún hook condicional ni tras un return temprano. El
// resto del estilo lo cubren tsc y los tests. `npm run lint`.
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['dist/**', 'auditoria/**', 'node_modules/**', 'convex/_generated/**'] },
  { linterOptions: { reportUnusedDisableDirectives: 'off' } },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { parser: tseslint.parser, parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } } },
    plugins: { 'react-hooks': reactHooks },
    rules: { 'react-hooks/rules-of-hooks': 'error' },
  },
];
