import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', 'node_modules/**']
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser
      }
    },
    rules: {
      // Stylistic / noisy rules stay warnings so they don't block CI
      'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
      'vue/multi-word-component-names': 'off',
      'vue/no-unused-vars': 'warn',
      // v-html is used deliberately with renderMarkdown, which escapes input
      'vue/no-v-html': 'off',
      // Catch template references to removed/renamed script identifiers
      'vue/no-undef-properties': 'error'
    }
  },
  {
    files: ['vite.config.js', 'eslint.config.js', 'vitest.config.js'],
    languageOptions: {
      globals: {
        ...globals.node
      }
    }
  }
]
