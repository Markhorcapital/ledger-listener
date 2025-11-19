/**
 * Markhor CEX Balance Updater for Google Sheets
 * 
 * This script fetches account balances from the FastAPI backend
 * and appends a new row with date and total balances for ALI and USDT.
 * 
 * Setup:
 * 1. Open your Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Copy this code
 * 4. Update CONFIG below with your settings
 * 5. Run setupTrigger() once to schedule daily 7 PM updates
 */

// ==================== CONFIGURATION ====================
const CONFIG = {
  // Backend API URL - USE SUMMARY ENDPOINT (faster, cleaner structure)
  API_URL: 'http://your-server-ip:8080/api/balances/summary',
  
  // Authentication token (from backend config.yml)
  AUTH_TOKEN: 'Ur2ZINGALaHYceS-DlVK4paC8LXXhMLPw-gLP3vTiGE',
  
  // Sheet name where balances will be updated
  SHEET_NAME: 'Sheet1',
  
  // Exchange and account structure mapping
  // Format: {exchange, accountName, aliCol, usdtCol}
  ACCOUNTS: [
    {exchange: 'Gate_io', accountName: 'MPMMS', usdtCol: 2, aliCol: 3},
    {exchange: 'MEXC', accountName: 'MPMM-MXC', usdtCol: 14, aliCol: 15},
    {exchange: 'HTX', accountName: 'MPMMSOne', usdtCol: 26, aliCol: 27},
    {exchange: 'Crypto_com', accountName: 'MPMMS', usdtCol: 34, aliCol: 35}
  ]
};

// ==================== MAIN FUNCTION ====================
/**
 * Main function to fetch and update balances
 * This will be called by the time-based trigger
 */
function updateBalances() {
  try {
    Logger.log('Starting balance update at ' + new Date());
    
    // Fetch data from API
    const balanceData = fetchBalancesFromAPI();
    
    if (!balanceData || !balanceData.success) {
      throw new Error('Failed to fetch balance data from API');
    }
    
    // Update sheet with data
    updateSheet(balanceData);
    
    Logger.log('Balance update completed successfully');
    
    // Optional: Send success notification
    // sendEmailNotification('Success', 'Balances updated successfully');
    
  } catch (error) {
    Logger.log('Error updating balances: ' + error.toString());
    
    // Optional: Send error notification
    // sendEmailNotification('Error', error.toString());
    
    throw error;
  }
}

// ==================== API FUNCTIONS ====================
/**
 * Fetch balance data from FastAPI backend
 */
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
/**
 * Add a new row with date and total balances to the sheet
 * Uses the SUMMARY endpoint structure: summary[Exchange][AccountName][Currency].total
 */
function updateSheet(balanceData) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAME);
  
  if (!sheet) {
    throw new Error('Sheet not found: ' + CONFIG.SHEET_NAME);
  }
  
  // Get current date (format: M/d/yyyy to match existing data)
  const now = new Date();
  const dateString = Utilities.formatDate(now, 'Asia/Karachi', 'M/d/yyyy');
  
  // Find the last row with data and add new row below it
  const lastRow = sheet.getLastRow();
  const newRow = lastRow + 1;
  
  // Extract summary data
  const summary = balanceData.summary;
  
  // Determine max column needed
  const maxCol = Math.max.apply(Math, CONFIG.ACCOUNTS.map(function(a) {
    return Math.max(a.usdtCol, a.aliCol);
  }));
  
  // Initialize row data array with empty values
  const rowData = [];
  for (let i = 0; i < maxCol; i++) {
    rowData.push('');
  }
  
  // Set date in first column (Column A = index 0)
  rowData[0] = dateString;
  
  // Fill in TOTAL balances for each configured account
  CONFIG.ACCOUNTS.forEach(function(accountConfig) {
    const exchange = accountConfig.exchange;
    const accountName = accountConfig.accountName;
    
    // Navigate: summary[Exchange][AccountName]
    if (summary[exchange] && summary[exchange][accountName]) {
      const accountBalances = summary[exchange][accountName];
      
      // USDT total balance
      if (accountBalances.USDT && accountBalances.USDT.total !== undefined) {
        rowData[accountConfig.usdtCol - 1] = accountBalances.USDT.total;
        Logger.log(exchange + ':' + accountName + ' - USDT: ' + accountBalances.USDT.total);
      } else if (accountBalances.USD && accountBalances.USD.total !== undefined) {
        // Crypto.com uses USD instead of USDT
        rowData[accountConfig.usdtCol - 1] = accountBalances.USD.total;
        Logger.log(exchange + ':' + accountName + ' - USD: ' + accountBalances.USD.total);
      } else {
        rowData[accountConfig.usdtCol - 1] = 0;
        Logger.log(exchange + ':' + accountName + ' - USDT/USD: 0 (not found)');
      }
      
      // ALI total balance
      if (accountBalances.ALI && accountBalances.ALI.total !== undefined) {
        rowData[accountConfig.aliCol - 1] = accountBalances.ALI.total;
        Logger.log(exchange + ':' + accountName + ' - ALI: ' + accountBalances.ALI.total);
      } else {
        rowData[accountConfig.aliCol - 1] = 0;
        Logger.log(exchange + ':' + accountName + ' - ALI: 0 (not found)');
      }
    } else {
      Logger.log('Warning: No balance data for ' + exchange + ':' + accountName);
      rowData[accountConfig.usdtCol - 1] = 0;
      rowData[accountConfig.aliCol - 1] = 0;
    }
  });
  
  // Write the new row to the sheet
  sheet.getRange(newRow, 1, 1, maxCol).setValues([rowData]);
  
  Logger.log('Added new row ' + newRow + ' with date: ' + dateString);
}

// ==================== TRIGGER SETUP ====================
/**
 * Set up time-based trigger for daily updates at 7 PM
 * Run this function once to create the trigger
 */
function setupTrigger() {
  // Delete existing triggers
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'updateBalances') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // Create new trigger for daily 7 PM (Pakistan Time = UTC+5)
  // Note: Apps Script uses the spreadsheet's timezone
  ScriptApp.newTrigger('updateBalances')
    .timeBased()
    .everyDays(1)
    .atHour(19)  // 7 PM
    .create();
  
  Logger.log('Trigger created successfully for daily 7 PM updates');
}

/**
 * Remove all triggers
 */
function removeTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'updateBalances') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  Logger.log('All triggers removed');
}

// ==================== UTILITY FUNCTIONS ====================
/**
 * Test API connection
 */
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

/**
 * Send email notification (optional)
 */
function sendEmailNotification(subject, message) {
  const recipient = Session.getActiveUser().getEmail();
  
  MailApp.sendEmail({
    to: recipient,
    subject: 'Markhor Balance Update: ' + subject,
    body: message + '\n\nTimestamp: ' + new Date()
  });
}

/**
 * Manual test function - run this to test the balance update without waiting for trigger
 */
function manualTest() {
  Logger.log('Running manual test...');
  updateBalances();
  Logger.log('Manual test completed');
}

