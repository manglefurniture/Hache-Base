'use strict';

const budgets = require('./budgets.json');

const assertions = Object.fromEntries(
  Object.entries(budgets.assertions).map(([audit, budget]) => {
    const {level, ...options} = budget;
    return [audit, [level, options]];
  }),
);

module.exports = {
  ci: {
    collect: {
      staticDistDir: './tests/browser/fixture',
      url: budgets.urls.map((pathname) => `http://localhost${pathname}`),
      numberOfRuns: budgets.profile.number_of_runs,
      settings: {
        onlyCategories: ['performance', 'accessibility'],
        chromeFlags: '--disable-dev-shm-usage',
      },
    },
    assert: {
      includePassedAssertions: true,
      assertions,
    },
    upload: {
      target: 'filesystem',
      outputDir: './artifacts/lighthouse',
    },
  },
};
