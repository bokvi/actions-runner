// Conventional Commits, as required by Dotykacka/docs-git (CONTRIBUTING.md#commit-messages).
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // docs-git: keep the whole subject line at 72 characters or fewer.
    'header-max-length': [2, 'always', 72],
  },
};
