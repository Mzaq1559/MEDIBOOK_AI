import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge, LoadingSpinner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import {
  sendChatMessage,
  formatChatTimestamp,
  getChatErrorMessage,
  isValidUuid,
  type ChatOptionItem,
  type ChatUiData,
} from '../services/chat';
import { DoctorCard } from '../components/chat/DoctorCard';
import { TimeSlotGrid } from '../components/chat/TimeSlotGrid';
import { ConfirmationCard } from '../components/chat/ConfirmationCard';
import { RescheduleConfirmation } from '../components/chat/RescheduleConfirmation';
import { AppointmentCard } from '../components/chat/AppointmentCard';

interface ChatMessage {
  id: string;
  sender: 'bot' | 'user';
  text?: string;
  timestamp: string;
  isEmergency?: boolean;
  requiresLogin?: boolean;
  optionItems?: ChatOptionItem[];
  uiData?: ChatUiData | null;
  nextAction?: string | null;
}

function mapApiResponseToBotMessage(
  response: Awaited<ReturnType<typeof sendChatMessage>>
): Omit<ChatMessage, 'id' | 'sender'> {
  const isEmergency = response.next_action === 'emergency_redirect';
  const requiresLogin = response.next_action === 'waiting_for_login';

  return {
    text: response.bot_message,
    timestamp: formatChatTimestamp(response.timestamp),
    isEmergency,
    requiresLogin,
    optionItems: response.options.length > 0 ? response.options : undefined,
    uiData: response.ui_data,
    nextAction: response.next_action,
  };
}

export const Chat: React.FC = () => {
  const { currentUser } = useAuth();
  const userName = currentUser?.name?.split(',')[0]?.split(' ')[0] || 'there';

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-welcome',
      sender: 'bot',
      text: `Hello ${userName}! I'm your MediBook AI Health Assistant. How can I help you today? You can describe symptoms to book an appointment, or ask to reschedule/cancel an existing one.`,
      timestamp: 'Just now',
    },
  ]);

  const [inputVal, setInputVal] = useState('');
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [isBookingInProgress, setIsBookingInProgress] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const patientId =
    currentUser?.userType === 'patient' && currentUser.id && isValidUuid(currentUser.id)
      ? currentUser.id
      : null;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isBotTyping]);

  const isDoctor = currentUser?.userType === 'doctor';

  const quickSymptoms = isDoctor
    ? [
        'Show my appointments',
        'Reschedule a patient\'s appointment',
        'Cancel a patient\'s appointment',
      ]
    : [
        'Book an appointment',
        'Cancel my appointment',
        'Reschedule appointment',
        'What are my appointments?',
      ];

  const callChatApi = useCallback(
    async (text: string, optionId?: string) => {
      const isConfirmMessage = /^(yes|confirm|yes,\s*confirm)/i.test(text.trim());

      setIsBotTyping(true);
      if (isConfirmMessage) {
        setIsBookingInProgress(true);
      }

      try {
        const messagePayload = optionId ? `${text} ${optionId}` : text;
        const response = await sendChatMessage({
          message: messagePayload,
          conversation_id: conversationId,
          patient_id: patientId,
        });

        setConversationId(response.conversation_id);

        const botMessage: ChatMessage = {
          id: `bot-${Date.now()}`,
          sender: 'bot',
          ...mapApiResponseToBotMessage(response),
        };

        setMessages((prev) => [...prev, botMessage]);
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          {
            id: `bot-error-${Date.now()}`,
            sender: 'bot',
            text: getChatErrorMessage(error),
            timestamp: formatChatTimestamp(),
          },
        ]);
      } finally {
        setIsBotTyping(false);
        setIsBookingInProgress(false);
      }
    },
    [conversationId, patientId]
  );

  const handleSendMessage = async (textToSend?: string, optionId?: string) => {
    const text = (textToSend || inputVal).trim();
    if (!text && !optionId) return;
    if (isBotTyping) return;

    if (!optionId || text) {
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        text,
        timestamp: formatChatTimestamp(),
      };
      setMessages((prev) => [...prev, userMessage]);
    }
    
    if (!textToSend) setInputVal('');

    await callChatApi(text, optionId);
  };

  const handleAction = (text: string, id?: string) => {
    handleSendMessage(text, id);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-surfaceContainerHigh">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-primary to-primaryContainer text-white flex items-center justify-center shadow-soft-sm shrink-0">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-heading font-extrabold text-xl sm:text-2xl text-textPrimary tracking-tight">
                AI Health Assistant
              </h1>
              <Badge status="success" size="sm" withDot>
                Online
              </Badge>
            </div>
            <p className="text-xs text-textSecondary">
              Describe your symptoms and I'll help you book the right appointment
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge status="primary" size="sm">
            Clinical Triage Model v3.0
          </Badge>
        </div>
      </div>

      {/* Chat Scrollable Container */}
      <Card
        radius="3xl"
        shadow="md"
        className="p-4 sm:p-6 bg-white/90 backdrop-blur-sm border border-surfaceContainerHigh min-h-[500px] max-h-[620px] overflow-y-auto flex flex-col justify-between space-y-6"
      >
        <div className="space-y-5">
          {messages.map((msg) => {
            if (msg.sender === 'user') {
              return (
                <div key={msg.id} className="flex justify-end items-end gap-2 animate-fadeIn">
                  <div className="flex flex-col items-end max-w-[85%] sm:max-w-[75%]">
                    <div className="bg-primary text-white p-3.5 sm:p-4 rounded-2xl rounded-tr-sm shadow-soft-sm text-sm leading-relaxed">
                      {msg.text}
                    </div>
                    <span className="text-[10px] text-textSecondary mt-1 px-1">{msg.timestamp}</span>
                  </div>
                </div>
              );
            }

            // Emergency Alert Message
            if (msg.isEmergency) {
              return (
                <div key={msg.id} className="flex justify-start items-start gap-3 animate-fadeIn">
                  <div className="w-8 h-8 rounded-xl bg-error text-white flex items-center justify-center shrink-0 mt-1 shadow-soft-sm">🚨</div>
                  <div className="w-full max-w-xl">
                    <div className="bg-errorContainer border-2 border-error/40 p-5 rounded-2xl rounded-tl-sm text-textPrimary shadow-soft-sm space-y-3">
                      <div className="flex items-center gap-2">
                        <span className="font-heading font-extrabold text-sm text-error uppercase tracking-wider">
                          Emergency Medical Alert
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-textPrimary leading-relaxed whitespace-pre-line">
                        {msg.text}
                      </p>
                      <div className="pt-2 flex flex-wrap gap-2.5">
                        <a href="tel:1122" className="inline-flex items-center gap-1.5 bg-error text-white text-xs font-bold px-4 py-2 rounded-pill hover:bg-[#a01616] shadow-soft transition-all">
                          📞 Call Emergency (1122)
                        </a>
                      </div>
                    </div>
                    <span className="text-[10px] text-textSecondary mt-1 px-1 block">{msg.timestamp}</span>
                  </div>
                </div>
              );
            }

            // Normal Bot Message
            return (
              <div key={msg.id} className="flex justify-start items-start gap-3 animate-fadeIn">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-primaryContainer text-white flex items-center justify-center shrink-0 mt-1 shadow-soft-sm text-xs font-bold">
                  AI
                </div>

                <div className="w-full max-w-2xl space-y-3">
                  {/* Bot text bubble */}
                  {msg.text && (
                    <div className="bg-gradient-to-br from-[#EFF4FF] to-[#E6EEFF] border border-primaryContainer/15 p-4 rounded-2xl rounded-tl-sm text-textPrimary text-sm leading-relaxed shadow-soft-sm whitespace-pre-line">
                      {msg.text}
                    </div>
                  )}

                  {/* Login required prompt */}
                  {msg.requiresLogin && (
                    <div className="pt-1">
                      <Link to="/login">
                        <Button size="sm" variant="primary">
                          Log in to continue
                        </Button>
                      </Link>
                    </div>
                  )}

                  {/* Structured UI rendering based on uiData */}
                  {msg.uiData?.doctors && msg.uiData.doctors.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                      {msg.uiData.doctors.map((doc) => (
                        <DoctorCard 
                          key={doc.doctor_id} 
                          doctor={doc} 
                          onClick={(id) => handleAction("Selected Doctor", id)}
                          disabled={isBotTyping}
                        />
                      ))}
                    </div>
                  )}

                  {msg.uiData?.slots && msg.uiData.slots.length > 0 && (
                    <div className="pt-2">
                      <TimeSlotGrid
                        slots={msg.uiData.slots}
                        onSelect={(ts) => handleAction("Selected Time Slot", ts)}
                        disabled={isBotTyping}
                      />
                    </div>
                  )}

                  {msg.uiData?.appointments && msg.uiData.appointments.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                      {msg.uiData.appointments.map((appt) => (
                        <AppointmentCard
                          key={appt.appointment_id}
                          appointment={appt}
                          onSelect={(msg.nextAction === 'show_appointments' && msg.text?.includes('cancel') === false && msg.text?.includes('reschedule') === false) ? undefined : (id) => handleAction("Selected Appointment", id)}
                          disabled={isBotTyping}
                        />
                      ))}
                    </div>
                  )}

                  {msg.uiData?.booking && (
                    <ConfirmationCard
                      booking={msg.uiData.booking}
                      isLoading={isBookingInProgress}
                      disabled={isBotTyping}
                      onConfirm={() => handleAction('yes, confirm')}
                      onChange={() => handleAction('change')}
                    />
                  )}

                  {msg.uiData?.reschedule && (
                    <RescheduleConfirmation
                      reschedule={msg.uiData.reschedule}
                      isLoading={isBookingInProgress}
                      disabled={isBotTyping}
                      onConfirm={() => handleAction('yes, confirm')}
                      onChange={() => handleAction('change')}
                    />
                  )}

                  <span className="text-[10px] text-textSecondary mt-1 px-1 block">{msg.timestamp}</span>
                </div>
              </div>
            );
          })}

          {/* Bot Typing indicator */}
          {isBotTyping && (
            <div className="flex items-center gap-2.5 text-xs text-textSecondary animate-fadeIn pl-2">
              <LoadingSpinner size="sm" color="primary" />
              <span>AI is thinking...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Chips */}
        <div className="pt-4 border-t border-surfaceContainerHigh">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-textSecondary">
              Suggestions:
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {quickSymptoms.map((symptom) => (
              <button
                key={symptom}
                type="button"
                onClick={() => handleSendMessage(symptom)}
                disabled={isBotTyping}
                className="text-xs bg-surfaceContainer hover:bg-surfaceContainerHigh text-textPrimary px-3 py-1.5 rounded-pill border border-surfaceContainerHigh transition-all focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
              >
                {symptom}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Message Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        className="bg-white p-2.5 sm:p-3 rounded-2xl sm:rounded-pill border border-surfaceContainerHigh shadow-soft flex items-center gap-2"
      >
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Type your message here..."
          className="flex-1 bg-transparent px-4 py-2 text-sm text-textPrimary placeholder:text-textSecondary/60 outline-none"
          disabled={isBotTyping}
        />

        <button
          type="submit"
          disabled={!inputVal.trim() || isBotTyping}
          className="w-10 h-10 rounded-pill bg-primary hover:bg-primaryContainer text-white flex items-center justify-center shrink-0 disabled:opacity-40 disabled:cursor-not-allowed shadow-soft-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="Send message"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
          </svg>
        </button>
      </form>
    </div>
  );
};
