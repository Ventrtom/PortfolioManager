import React from 'react';
import { NATURAL_LANGUAGE_EXAMPLES } from '../../config/transactionFormConfig';
import ParsedPreview from './ParsedPreview';
import type { ParsedTransaction } from '../../types';

interface NaturalLanguageInputProps {
  transactionType: string;
  naturalLanguageInput: string;
  onInputChange: (value: string) => void;
  onTypeChange: (type: string) => void;
  onParse: () => void;
  parsedTransaction: ParsedTransaction | null;
  parseError: string | null;
  parsingState: 'idle' | 'parsing' | 'success' | 'error';
}

const NaturalLanguageInput: React.FC<NaturalLanguageInputProps> = ({
  transactionType,
  naturalLanguageInput,
  onInputChange,
  onTypeChange,
  onParse,
  parsedTransaction,
  parseError,
  parsingState
}) => {
  const examples = NATURAL_LANGUAGE_EXAMPLES[transactionType] || [];

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onParse();
    }
  };

  return (
    <div className="natural-language-section">
      <div className="nl-header">
        <h3>Natural Language Input</h3>
        <div className="nl-type-selector">
          <label htmlFor="nl-transaction-type">Transaction Type:</label>
          <select
            id="nl-transaction-type"
            value={transactionType}
            onChange={(e) => onTypeChange(e.target.value)}
            className="form-select"
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
            <option value="DIVIDEND">DIVIDEND</option>
            <option value="FEE">FEE</option>
            <option value="TAX">TAX</option>
          </select>
        </div>
      </div>

      <div className="nl-input-group">
        <label htmlFor="nl-input">Enter transaction details:</label>
        <input
          id="nl-input"
          type="text"
          value={naturalLanguageInput}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={`e.g., ${examples[0] || 'BUY - AAPL - 100 - @150.50 - 01/15/2025'}`}
          className="form-input nl-input"
        />
        <button
          type="button"
          onClick={onParse}
          disabled={!naturalLanguageInput.trim() || parsingState === 'parsing'}
          className="btn btn-secondary parse-button"
        >
          {parsingState === 'parsing' ? 'Parsing...' : 'Parse'}
        </button>
      </div>

      {examples.length > 0 && (
        <div className="nl-examples">
          <div className="nl-examples__header">
            <span aria-hidden="true">💡</span>
            <span>Format Examples for {transactionType}:</span>
          </div>
          <ul className="nl-examples__list">
            {examples.map((example, idx) => (
              <li key={idx} className="nl-examples__item">
                {example}
              </li>
            ))}
          </ul>
        </div>
      )}

      <ParsedPreview
        parsedTransaction={parsedTransaction}
        parseError={parseError}
        parsingState={parsingState}
      />
    </div>
  );
};

export default NaturalLanguageInput;
