/**
 * Markhor DEX Balance Updater
 *
 * Fetches on-chain balances from the /api/dex/balances endpoint and updates
 * the "DEX-ARB-Ledger" sheet to mirror the manual CSV layout.
 */

const DEX_CONFIG = {
  API_URL: 'http://13.213.155.171:8080/api/dex/balances',
  AUTH_TOKEN: 'Ur2ZINGALaHYceS-DlVK4paC8LXXhMLPw-gLP3vTiGE',
  SHEET_NAME: 'DEX-ARB-Ledger',
  TIMEZONE: 'Asia/Karachi',
  CHAIN_SECTIONS: [
    {
      apiKey: 'ethereum',
      wallets: [
        { label: 'ETH-ARB-V2', columns: { ALI: 2, USDC: 3, ETH: 4 } },
        { label: 'ETH-ARB-V3', columns: { ALI: 5, WETH: 6, ETH: 7 } },
        { label: 'MAIN', columns: { ALI: 8, USDC: 9, WETH: 10, ETH: 11 } }
      ],
      totals: { ALI: 12, USDC: 13, WETH: 14, ETH: 15 }
    },
    {
      apiKey: 'base',
      wallets: [
        { label: 'ETH-ARB-V2', columns: { ALI: 16, WETH: 17, ETH: 18 } },
        { label: 'MAIN', columns: { ALI: 19, WETH: 20, ETH: 21 } }
      ],
      totals: { ALI: 22, WETH: 23, ETH: 24 }
    },
    {
      apiKey: 'polygon',
      wallets: [
        { label: 'ETH-ARB-V2', columns: { ALI: 25, WPOL: 26, POL: 27 } },
        { label: 'MAIN', columns: { ALI: 28, WPOL: 29, POL: 30 } }
      ],
      totals: { ALI: 31, WPOL: 32, POL: 33 }
    },
    {
      apiKey: 'solana',
      wallets: [
        { label: 'SOL-ARB', columns: { ALI: 34, USDC: 35, SOL: 36 } },
        { label: 'MAIN', columns: { ALI: 37, USDC: 38, SOL: 39 } }
      ],
      totals: { ALI: 40, USDC: 41, SOL: 42 }
    }
  ],
  ALL_SECTION: {
    ALI: 43,
    USDC: 44,
    WETH: 45,
    WPOL: 46,
    ETH: 47,
    SOL: 48,
    POL: 49
  },
  PRICE_SECTION: {
    ALI: 50,
    ETH: 51,
    POL: 52,
    SOL: 53
  },
  CUMULATIVE_USD_COL: 54,
  COMMENTS_COL: 55
};

function updateDexBalances() {
  Logger.log('Starting DEX balance update at ' + new Date());
  const apiData = fetchDexBalancesFromAPI();
  if (!apiData || !apiData.success) {
    throw new Error('DEX API returned invalid payload');
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(DEX_CONFIG.SHEET_NAME);
  if (!sheet) {
    throw new Error('Sheet not found: ' + DEX_CONFIG.SHEET_NAME);
  }

  const lastRow = sheet.getLastRow();
  sheet.insertRowsAfter(lastRow, 1);
  const newRow = lastRow + 1;
  const now = new Date();
  const dateString = Utilities.formatDate(now, DEX_CONFIG.TIMEZONE, 'M/d/yyyy');
  sheet.getRange(newRow, 1).setValue(dateString);

  const allTotals = initAllTotals();

  DEX_CONFIG.CHAIN_SECTIONS.forEach(function(section) {
    const chainData = (apiData.chains && apiData.chains[section.apiKey]) || { wallets: {} };
    const chainTotals = {};

    section.wallets.forEach(function(walletCfg) {
      const walletEntry = chainData.wallets ? chainData.wallets[walletCfg.label] : null;
      const walletBalances = (walletEntry && walletEntry.balances) || {};

      Object.keys(walletCfg.columns).forEach(function(asset) {
        const colIndex = walletCfg.columns[asset];
        const value = toNumber(walletBalances[asset]);
        sheet.getRange(newRow, colIndex).setValue(value);

        chainTotals[asset] = (chainTotals[asset] || 0) + value;
        allTotals[asset] = (allTotals[asset] || 0) + value;
      });
    });

    if (section.totals) {
      Object.keys(section.totals).forEach(function(asset) {
        const colIndex = section.totals[asset];
        const totalValue = chainTotals[asset] || 0;
        sheet.getRange(newRow, colIndex).setValue(totalValue);
      });
    }
  });

  writeAllSection(sheet, newRow, allTotals);
  writePriceSection(sheet, newRow, apiData.prices || {});
  writeCumulativeAndComments(sheet, newRow, allTotals, apiData.prices || {});

  Logger.log('DEX balance update completed successfully');
}

function fetchDexBalancesFromAPI() {
  const options = {
    method: 'get',
    headers: {
      'Authorization': 'Bearer ' + DEX_CONFIG.AUTH_TOKEN,
      'Content-Type': 'application/json'
    },
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(DEX_CONFIG.API_URL, options);
  if (response.getResponseCode() !== 200) {
    throw new Error('DEX API returned status code ' + response.getResponseCode());
  }
  return JSON.parse(response.getContentText());
}

function initAllTotals() {
  return {
    ALI: 0,
    USDC: 0,
    WETH: 0,
    WPOL: 0,
    ETH: 0,
    SOL: 0,
    POL: 0
  };
}

function writeAllSection(sheet, rowIndex, allTotals) {
  Object.keys(DEX_CONFIG.ALL_SECTION).forEach(function(asset) {
    const colIndex = DEX_CONFIG.ALL_SECTION[asset];
    sheet.getRange(rowIndex, colIndex).setValue(allTotals[asset] || 0);
  });
}

function writePriceSection(sheet, rowIndex, prices) {
  const aliCell = sheet.getRange(rowIndex, DEX_CONFIG.PRICE_SECTION.ALI);
  aliCell.setValue(toNumber(prices.ALI));
  aliCell.setNumberFormat('0.00000000');

  const ethCell = sheet.getRange(rowIndex, DEX_CONFIG.PRICE_SECTION.ETH);
  ethCell.setValue(toNumber(prices.ETH));
  ethCell.setNumberFormat('0.00');

  const polCell = sheet.getRange(rowIndex, DEX_CONFIG.PRICE_SECTION.POL);
  polCell.setValue(toNumber(prices.POL));
  polCell.setNumberFormat('0.0000');

  const solCell = sheet.getRange(rowIndex, DEX_CONFIG.PRICE_SECTION.SOL);
  solCell.setValue(toNumber(prices.SOL));
  solCell.setNumberFormat('0.00');
}

function writeCumulativeAndComments(sheet, rowIndex, totals, prices) {
  const aliPrice = toNumber(prices.ALI);
  const ethPrice = toNumber(prices.ETH);
  const polPrice = toNumber(prices.POL);
  const solPrice = toNumber(prices.SOL);

  const aliUsdValuation = (totals.ALI || 0) * aliPrice;
  const quoteUsd =
    (totals.USDC || 0) +
    ((totals.WETH || 0) + (totals.ETH || 0)) * ethPrice +
    (totals.WPOL || 0) * polPrice +
    (totals.POL || 0) * polPrice +
    (totals.SOL || 0) * solPrice;

  const cumulativeUsd = aliUsdValuation + quoteUsd;
  const cumulativeCell = sheet.getRange(rowIndex, DEX_CONFIG.CUMULATIVE_USD_COL);
  cumulativeCell.setValue(cumulativeUsd);
  cumulativeCell.setNumberFormat('0.00');

  let comment = '';
  if (cumulativeUsd > 0) {
    if (quoteUsd > aliUsdValuation) {
      comment = 'Scewed towards USDT';
    } else if (quoteUsd < aliUsdValuation) {
      comment = 'Scewed towards ALI';
    } else {
      comment = 'Balanced';
    }
  }
  sheet.getRange(rowIndex, DEX_CONFIG.COMMENTS_COL).setValue(comment);
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') {
    return 0;
  }
  const parsed = parseFloat(value);
  return isNaN(parsed) ? 0 : parsed;
}

