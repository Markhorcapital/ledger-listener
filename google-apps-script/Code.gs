/**
 * Markhor CEX Balance Updater for Google Sheets - Dynamic Version
 * 
 * This script fetches ALL account balances from the FastAPI backend,
 * dynamically maps them to sheet columns, carries forward previous balances
 * for accounts without API keys, and calculates totals automatically.
 * 
 * Setup:
 * 1. Open your Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Copy this code
 * 4. Update CONFIG below with your settings
 * 5. Run updateBalances() manually anytime to update
 */

// ==================== CONFIGURATION ====================
const CONFIG = {
  // Backend API URL
  API_URL: 'http://13.213.155.171:8080/api/balances',
  
  // Authentication token
  AUTH_TOKEN: 'Ur2ZINGALaHYceS-DlVK4paC8LXXhMLPw-gLP3vTiGE',
  
  // Sheet name
  SHEET_NAME: 'Internal Ledger',
  
  // Timezone
  TIMEZONE: 'Asia/Karachi',
  
  // Column mapping structure based on sheet layout
  // Row 1: Exchange names (Gate.io at col 2, MEXC at col 14, HTX at col 26, CRYPTO at col 38)
  // Row 2: Account names under each exchange
  EXCHANGES: [
    {
      name: 'Gate_io',
      startCol: 2,
      accounts: [
        {name: 'MPMMS', aliCol: 2, quoteCol: 3, hasApiKey: true},
        {name: 'MARB1', aliCol: 4, quoteCol: 5, hasApiKey: false},
        {name: 'MXEMM', aliCol: 6, quoteCol: 7, hasApiKey: false},
        {name: 'MMARKHOR', aliCol: 8, quoteCol: 9, hasApiKey: false},
        {name: 'MAIN', aliCol: 10, quoteCol: 11, hasApiKey: false},
        {name: 'Total', aliCol: 12, quoteCol: 13, isTotal: true}
      ],
      quoteAsset: 'USDT'
    },
    {
      name: 'MEXC',
      startCol: 14,
      accounts: [
        {name: 'MPMM-MXC', aliCol: 14, quoteCol: 15, hasApiKey: true},
        {name: 'MARB1111', aliCol: 16, quoteCol: 17, hasApiKey: false},
        {name: 'MXEMM111', aliCol: 18, quoteCol: 19, hasApiKey: false},
        {name: 'MMARKHOR', aliCol: 20, quoteCol: 21, hasApiKey: false},
        {name: 'MAIN', aliCol: 22, quoteCol: 23, hasApiKey: false},
        {name: 'Total', aliCol: 24, quoteCol: 25, isTotal: true}
      ],
      quoteAsset: 'USDT'
    },
    {
      name: 'HTX',
      startCol: 26,
      accounts: [
        {name: 'MPMMSOne', aliCol: 26, quoteCol: 27, hasApiKey: true},
        {name: 'MARBOne', aliCol: 28, quoteCol: 29, hasApiKey: false},
        {name: 'MXEMMOne', aliCol: 30, quoteCol: 31, hasApiKey: false},
        {name: 'MMARKHOR', aliCol: 32, quoteCol: 33, hasApiKey: false},
        {name: 'MAIN', aliCol: 34, quoteCol: 35, hasApiKey: false},
        {name: 'Total', aliCol: 36, quoteCol: 37, isTotal: true}
      ],
      quoteAsset: 'USDT'
    },
    {
      name: 'Crypto_com',
      startCol: 38,
      accounts: [
        {name: 'MPMMS', aliCol: 38, quoteCol: 39, hasApiKey: true},
        {name: 'MAIN', aliCol: 40, quoteCol: 41, hasApiKey: false},
        {name: 'Total', aliCol: 42, quoteCol: 43, isTotal: true}
      ],
      quoteAsset: 'USD'  // Crypto.com uses USD, not USDT
    }
  ],
  // Cumulative totals columns (ALI + quote across all exchanges)
  CUMULATIVE: {
    aliCol: 44,              // Column AR (sum of Gate, MEXC, HTX, Crypto ALI totals)
    quoteCol: 45,            // Column AS (sum of Gate, MEXC, HTX USDT totals + Crypto USD)
    aliUsdValCol: 46,        // Column AT - ALI USD Valuation
    cumulativeUsdValCol: 47, // Column AU - Cumulative USD Valuation
    imbalanceCol: 48,        // Column AV - Imbalance %
    commentsCol: 49,         // Column AW - Comments based on imbalance
    priceCol: 50             // Column AX - ALI/USD price from CoinGecko
  }
};

// ==================== MAIN FUNCTION ====================
function updateBalances() {
  try {
    Logger.log('Starting balance update at ' + new Date());
    
    const balanceData = fetchBalancesFromAPI();
    
    if (!balanceData || !balanceData.success) {
      throw new Error('Failed to fetch balance data from API');
    }
    
    updateSheet(balanceData);
    
    Logger.log('Balance update completed successfully');
    
  } catch (error) {
    Logger.log('Error updating balances: ' + error.toString());
    throw error;
  }
}

// ==================== API FUNCTIONS ====================
function fetchBalancesFromAPI() {
  const options = {
    'method': 'get',
    'headers': {
      'Authorization': 'Bearer ' + CONFIG.AUTH_TOKEN,
      'Content-Type': 'application/json'
    },
    'muteHttpExceptions': true
  };
  
  try {
    const response = UrlFetchApp.fetch(CONFIG.API_URL, options);
    const statusCode = response.getResponseCode();
    
    if (statusCode !== 200) {
      throw new Error('API returned status code: ' + statusCode);
    }
    
    const data = JSON.parse(response.getContentText());
    return data;
    
  } catch (error) {
    Logger.log('API fetch error: ' + error.toString());
    throw error;
  }
}

// ==================== SHEET FUNCTIONS ====================
function updateSheet(balanceData) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) {
    throw new Error('Sheet not found: ' + CONFIG.SHEET_NAME);
  }

  // Build index of API balances by exchange:accountName
  const apiBalances = buildBalanceIndex(balanceData.accounts || []);

  // Get current date
  const now = new Date();
  const dateString = Utilities.formatDate(now, CONFIG.TIMEZONE, 'M/d/yyyy');

  // Get last row and create new row
  const lastRow = sheet.getLastRow();
  sheet.insertRowsAfter(lastRow, 1);
  const newRow = lastRow + 1;

  // Set date in column A
  sheet.getRange(newRow, 1).setValue(dateString);

  // Get previous non-empty row data for carrying forward balances
  // Need to loop backwards to find last row with actual data (skip weekends/empty rows)
  const maxCol = 50; // Max column we care about (up to PRICE column)
  const previousRowData = getPreviousNonEmptyRowData(sheet, lastRow, maxCol);
  const cumulativeConfig = CONFIG.CUMULATIVE || {};

  // Process each exchange
  let cumulativeAli = 0;
  let cumulativeQuote = 0;

  CONFIG.EXCHANGES.forEach(function(exchangeConfig) {
    const exchangeName = exchangeConfig.name;
    const quoteAsset = exchangeConfig.quoteAsset;
    
    // Track totals for this exchange
    let totalAli = 0;
    let totalQuote = 0;
    
    exchangeConfig.accounts.forEach(function(accountConfig) {
      if (accountConfig.isTotal) {
        // This is the Total column - write the accumulated totals
        sheet.getRange(newRow, accountConfig.aliCol).setValue(totalAli);
        sheet.getRange(newRow, accountConfig.quoteCol).setValue(totalQuote);
        Logger.log(exchangeName + ' Total - ALI: ' + totalAli + ' | ' + quoteAsset + ': ' + totalQuote);
        cumulativeAli += totalAli;
        cumulativeQuote += totalQuote;
      } else if (accountConfig.hasApiKey) {
        // This account has API key - fetch from API
        const key = makeBalanceKey(exchangeName, accountConfig.name);
        const accountData = apiBalances[key];
        
        let aliBalance = 0;
        let quoteBalance = 0;
        
        if (accountData && accountData.balances) {
          aliBalance = getCurrencyTotal(accountData.balances, 'ALI');
          quoteBalance = getCurrencyTotal(accountData.balances, quoteAsset);
          Logger.log(exchangeName + ':' + accountConfig.name + ' (API) - ALI: ' + aliBalance + ' | ' + quoteAsset + ': ' + quoteBalance);
        } else {
          Logger.log('Warning: No API data for ' + key + ', using 0');
        }
        
        sheet.getRange(newRow, accountConfig.aliCol).setValue(aliBalance);
        sheet.getRange(newRow, accountConfig.quoteCol).setValue(quoteBalance);
        
        totalAli += aliBalance;
        totalQuote += quoteBalance;
        
      } else {
        // This account has no API key - carry forward from previous row
        const prevAli = parseNumericValue(previousRowData[accountConfig.aliCol - 1]);
        const prevQuote = parseNumericValue(previousRowData[accountConfig.quoteCol - 1]);
        
        sheet.getRange(newRow, accountConfig.aliCol).setValue(prevAli);
        sheet.getRange(newRow, accountConfig.quoteCol).setValue(prevQuote);
        
        totalAli += prevAli;
        totalQuote += prevQuote;
        
        Logger.log(exchangeName + ':' + accountConfig.name + ' (Carried) - ALI: ' + prevAli + ' | ' + quoteAsset + ': ' + prevQuote);
      }
    });
  });

  // Write cumulative totals if configured
  if (cumulativeConfig.aliCol) {
    sheet.getRange(newRow, cumulativeConfig.aliCol).setValue(cumulativeAli);
  }
  if (cumulativeConfig.quoteCol) {
    sheet.getRange(newRow, cumulativeConfig.quoteCol).setValue(cumulativeQuote);
  }

  // Fetch ALI price from API response (fallback to previous row value)
  let aliPriceFromApi = null;
  if (balanceData && balanceData.pricing && balanceData.pricing.price_usd !== undefined) {
    aliPriceFromApi = Number(balanceData.pricing.price_usd);
  }
  const previousPriceValue = cumulativeConfig.priceCol
    ? parseNumericValue(previousRowData[cumulativeConfig.priceCol - 1])
    : 0;
  let aliPrice = !isNaN(aliPriceFromApi) && aliPriceFromApi !== null ? aliPriceFromApi : previousPriceValue;
  if (!isFinite(aliPrice)) {
    aliPrice = 0;
  }

  if (cumulativeConfig.priceCol) {
    const priceCell = sheet.getRange(newRow, cumulativeConfig.priceCol);
    priceCell.setValue(aliPrice);
    priceCell.setNumberFormat('0.00000000'); // show full precision (8 decimals)
  }

  // Calculate ALI USD valuation and cumulative USD valuation
  const aliUsdValuation = cumulativeAli * aliPrice;
  if (cumulativeConfig.aliUsdValCol) {
    const valuationCell = sheet.getRange(newRow, cumulativeConfig.aliUsdValCol);
    valuationCell.setValue(aliUsdValuation);
    valuationCell.setNumberFormat('0.00');
  }

  const cumulativeUsdValuation = aliUsdValuation + cumulativeQuote;
  if (cumulativeConfig.cumulativeUsdValCol) {
    const cumulativeCell = sheet.getRange(newRow, cumulativeConfig.cumulativeUsdValCol);
    cumulativeCell.setValue(cumulativeUsdValuation);
    cumulativeCell.setNumberFormat('0.00');
  }

  // Imbalance % measures deviation from a 50/50 ALI-vs-Quote USD allocation
  let imbalancePercent = 0;
  if (cumulativeUsdValuation > 0) {
    const quotePercentage = (cumulativeQuote / cumulativeUsdValuation) * 100;
    imbalancePercent = Math.abs(quotePercentage - 50) * 2;
  }
  if (cumulativeConfig.imbalanceCol) {
    const imbalanceCell = sheet.getRange(newRow, cumulativeConfig.imbalanceCol);
    imbalanceCell.setValue(imbalancePercent);
    imbalanceCell.setNumberFormat('0.00');
  }

  // Comments describe which side of the portfolio dominates (based on USD value)
  let imbalanceComment = '';
  if (cumulativeUsdValuation > 0) {
    if (cumulativeQuote > aliUsdValuation) {
      imbalanceComment = 'Scewed towards USDT';
    } else if (cumulativeQuote < aliUsdValuation) {
      imbalanceComment = 'Scewed towards ALI';
    } else {
      imbalanceComment = 'Balanced';
    }
  }
  if (cumulativeConfig.commentsCol) {
    sheet.getRange(newRow, cumulativeConfig.commentsCol).setValue(imbalanceComment);
  }

  Logger.log('Added new row ' + newRow + ' (' + dateString + ') in sheet "' + CONFIG.SHEET_NAME + '"');
}

// Build index of API balances: {Exchange::AccountName: accountData}
function buildBalanceIndex(accounts) {
  const index = {};
  accounts.forEach(function(account) {
    const key = makeBalanceKey(account.exchange, account.account_name);
    if (key) {
      index[key] = account;
    }
  });
  return index;
}

// Create consistent key for balance lookup (case-insensitive, trimmed)
function makeBalanceKey(exchange, accountName) {
  if (!exchange || !accountName) {
    return '';
  }
  const normalizedExchange = exchange.toString().trim().toLowerCase();
  const normalizedAccount = accountName.toString().trim().toLowerCase();
  return normalizedExchange + '::' + normalizedAccount;
}

// Get total balance for a currency from balance map
function getCurrencyTotal(balanceMap, symbol) {
  if (!symbol || !balanceMap || !balanceMap[symbol]) {
    return 0;
  }
  const currencyInfo = balanceMap[symbol];
  return currencyInfo.total !== undefined ? currencyInfo.total : 0;
}

// Parse numeric values from sheet cells (handles commas)
function parseNumericValue(value) {
  if (value === null || value === undefined || value === '') {
    return 0;
  }
  const cleaned = String(value).replace(/,/g, '');
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? 0 : parsed;
}

// Get previous non-empty row data, searching backwards through empty rows
function getPreviousNonEmptyRowData(sheet, startRow, maxCol) {
  // Start from the row before the new row (the last row)
  // Loop backwards up to 30 rows (to cover weekends + holidays)
  const maxRowsToCheck = 30;
  
  for (let rowOffset = 0; rowOffset < maxRowsToCheck; rowOffset++) {
    const checkRow = startRow - rowOffset;
    
    // Don't go before row 3 (rows 1-2 are headers)
    if (checkRow < 3) {
      Logger.log('Warning: Reached header rows, no previous data found');
      // Return empty array
      return new Array(maxCol).fill(0);
    }
    
    const rowData = sheet.getRange(checkRow, 1, 1, maxCol).getValues()[0];
    
    // Check if this row has data (check if date column and some balance columns are not empty)
    // Check columns 2, 14, 26, 38 (first ALI columns of each exchange)
    const hasData = rowData[0] && // Date column
                    (rowData[1] || rowData[13] || rowData[25] || rowData[37]); // At least one ALI value
    
    if (hasData) {
      Logger.log('Found previous non-empty row at: ' + checkRow + ' (offset: ' + rowOffset + ')');
      return rowData;
    }
  }
  
  // If no data found in last 30 rows, return zeros
  Logger.log('Warning: No non-empty row found in last ' + maxRowsToCheck + ' rows');
  return new Array(maxCol).fill(0);
}

// ==================== UTILITY FUNCTIONS ====================
function testAPIConnection() {
  try {
    const data = fetchBalancesFromAPI();
    Logger.log('API Connection Test: SUCCESS');
    Logger.log('Total accounts: ' + data.total_accounts);
    Logger.log('Successful fetches: ' + data.successful_fetches);
    Logger.log('Failed fetches: ' + data.failed_fetches);
    return true;
  } catch (error) {
    Logger.log('API Connection Test: FAILED');
    Logger.log('Error: ' + error.toString());
    return false;
  }
}

function sendEmailNotification(subject, message) {
  const recipient = Session.getActiveUser().getEmail();
  
  MailApp.sendEmail({
    to: recipient,
    subject: 'Markhor Balance Update: ' + subject,
    body: message + '\n\nTimestamp: ' + new Date()
  });
}

function manualTest() {
  Logger.log('Running manual test...');
  updateBalances();
  Logger.log('Manual test completed');
}
