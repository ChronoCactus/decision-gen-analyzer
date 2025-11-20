module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation changes
        'style',    // Code style changes (formatting, no logic change)
        'refactor', // Code refactoring (no feature change)
        'perf',     // Performance improvements
        'test',     // Adding or updating tests
        'chore',    // Build process, tooling, dependencies
        'ci',       // CI/CD changes
        'revert',   // Revert a previous commit
      ],
    ],
    'type-case': [2, 'always', 'lower-case'],
    'type-empty': [2, 'never'],
    'subject-empty': [2, 'never'],
    'subject-case': [0], // Allow any case in subject
    'header-max-length': [2, 'always', 100],
  },
};
