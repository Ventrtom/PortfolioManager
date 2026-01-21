import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './ManualReviewChat.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface SuggestedAction {
  type: string;
  label: string;
  ticker?: string;
}

interface ManualReviewChatProps {
  ticker: string;
  onClose: () => void;
  onResolved: () => void;
}

const ManualReviewChat = ({ ticker, onClose, onResolved }: ManualReviewChatProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState<SuggestedAction[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Start manual review session
    const startSession = async () => {
      try {
        const response = await axios.get(
          `http://localhost:8000/api/stocks/${ticker}/manual-review/start`
        );

        // Add initial AI message
        setMessages([
          {
            role: 'assistant',
            content: response.data.initial_message,
          },
        ]);
      } catch (error) {
        console.error('Failed to start manual review:', error);
        setMessages([
          {
            role: 'assistant',
            content: `Failed to start review session for ${ticker}. Please try again.`,
          },
        ]);
      }
    };

    startSession();
  }, [ticker]);

  const sendMessage = async (message: string) => {
    if (!message.trim()) return;

    // Add user message
    const newUserMessage: Message = {
      role: 'user',
      content: message,
    };
    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue('');
    setLoading(true);

    try {
      // Send to backend
      const response = await axios.post(
        `http://localhost:8000/api/stocks/${ticker}/manual-review/chat`,
        {
          message: message,
          conversation_history: messages,
        }
      );

      // Add AI response
      const aiMessage: Message = {
        role: 'assistant',
        content: response.data.message,
      };
      setMessages((prev) => [...prev, aiMessage]);

      // Check if AI executed a save action
      if (response.data.executed_action?.type === 'save_mapping') {
        // AI successfully saved the mapping - clear actions and close after delay
        setSuggestedActions([]);
        setTimeout(() => {
          onResolved();
          onClose();
        }, 2000);
      } else {
        // Update suggested actions for normal responses
        setSuggestedActions(response.data.suggested_actions || []);
      }
    } catch (error: any) {
      console.error('Chat error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveMapping = async (resolvedTicker: string) => {
    setLoading(true);

    try {
      await axios.post(
        `http://localhost:8000/api/stocks/${ticker}/manual-review/save`,
        {
          resolved_ticker: resolvedTicker,
        }
      );

      // Add success message
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `✓ Successfully saved mapping: ${ticker} → ${resolvedTicker}. The stock data has been updated!`,
        },
      ]);

      // Clear suggested actions
      setSuggestedActions([]);

      // Notify parent after a short delay
      setTimeout(() => {
        onResolved();
        onClose();
      }, 2000);
    } catch (error: any) {
      console.error('Save error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `✗ Failed to save mapping: ${error.response?.data?.detail || error.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestedAction = (action: SuggestedAction) => {
    if (action.type === 'save_mapping' && action.ticker) {
      handleSaveMapping(action.ticker);
    } else if (action.type === 'check_ticker') {
      // Prompt user to enter a ticker
      const newTicker = prompt('Enter ticker symbol to check:');
      if (newTicker) {
        sendMessage(`Check ${newTicker.toUpperCase()}`);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputValue);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="manual-review-chat" onClick={(e) => e.stopPropagation()}>
        <div className="chat-header">
          <h3>Manual Review: {ticker}</h3>
          <button onClick={onClose} className="close-btn">
            ×
          </button>
        </div>

        <div className="chat-messages">
          {messages.map((msg, index) => (
            <div key={index} className={`chat-message ${msg.role}`}>
              <div className="message-content">
                {msg.content.split('\n').map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message assistant">
              <div className="message-content typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Actions */}
        {suggestedActions.length > 0 && (
          <div className="suggested-actions">
            {suggestedActions.map((action, index) => (
              <button
                key={index}
                onClick={() => handleSuggestedAction(action)}
                className="suggested-action-btn"
                disabled={loading}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="chat-input-form">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            className="chat-input"
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="send-btn" disabled={loading || !inputValue.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
};

export default ManualReviewChat;
