import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge, LoadingSpinner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import {
  sendChatMessage,
  parseDoctorOptionsFromMessage,
  parseBookingSummary,
  parseConfirmedBooking,
  formatChatTimestamp,
  getChatErrorMessage,
  isValidUuid,
  type ChatOptionItem,
  type ParsedDoctorOption,
} from '../services/chat';

interface ChatMessage {
  id: string;
  sender: 'bot' | 'user';
  text?: string;
  timestamp: string;
  isEmergency?: boolean;
  requiresLogin?: boolean;
  doctors?: ParsedDoctorOption[];
  optionItems?: ChatOptionItem[];
  bookingSummary?: {
    doctor: ParsedDoctorOption;
    selectedSlot: string;
    isConfirmed?: boolean;
  };
}

function mapApiResponseToBotMessage(
  response: Awaited<ReturnType<typeof sendChatMessage>>
): Omit<ChatMessage, 'id' | 'sender'> {
  const isEmergency = response.next_action === 'emergency_redirect';
  const requiresLogin = response.next_action === 'waiting_for_login';

  let doctors: ParsedDoctorOption[] | undefined;
  if (
    response.next_action === 'waiting_for_doctor_selection' ||
    response.next_action === 'waiting_for_new_time'
  ) {
    const parsed = parseDoctorOptionsFromMessage(response.bot_message, response.options);
    doctors = parsed.length > 0 ? parsed : undefined;
  }

  let bookingSummary: ChatMessage['bookingSummary'];
  if (response.next_action === 'waiting_for_confirmation') {
    bookingSummary = parseBookingSummary(response.bot_message) ?? undefined;
  } else if (response.next_action === 'appointment_booked') {
    bookingSummary = parseConfirmedBooking(response.bot_message) ?? undefined;
    if (bookingSummary) {
      bookingSummary.isConfirmed = true;
    }
  }

  return {
    text: response.bot_message,
    timestamp: formatChatTimestamp(response.timestamp),
    isEmergency,
    requiresLogin,
    doctors,
    optionItems: response.options.length > 0 ? response.options : undefined,
    bookingSummary,
  };
}

export const Chat: React.FC = () => {
  const { currentUser } = useAuth();
  const userName = currentUser?.name?.split(',')[0]?.split(' ')[0] || 'there';

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-welcome',
      sender: 'bot',
      text: `Hello ${userName}! I'm your MediBook AI Health Assistant. Please describe what symptoms or discomfort you are experiencing today, and I'll help assess severity and match you with the right specialist.`,
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

  const quickSymptoms = [
    'Persistent cough & low fever',
    'Severe migraine with light sensitivity',
    'Lower back pain after lifting',
    '🚨 Severe chest pain & shortness of breath',
  ];

  const callChatApi = useCallback(
    async (text: string) => {
      const isConfirmMessage = /^(yes|confirm|yes,\s*confirm)/i.test(text.trim());

      setIsBotTyping(true);
      if (isConfirmMessage) {
        setIsBookingInProgress(true);
      }

      try {
        const response = await sendChatMessage({
          message: text,
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

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputVal).trim();
    if (!text || isBotTyping) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: formatChatTimestamp(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!textToSend) setInputVal('');

    await callChatApi(text);
  };

  const handleSelectDoctorSlot = (doctor: ParsedDoctorOption, slot: string) => {
    const message = `${doctor.name} at ${slot}`;
    handleSendMessage(message);
  };

  const handleOptionClick = (option: ChatOptionItem) => {
    handleSendMessage(option.text);
  };

  const handleConfirmBooking = () => {
    handleSendMessage('yes, confirm');
  };

  const handleChangeBooking = () => {
    handleSendMessage('No, I would like to pick a different doctor and time.');
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-surfaceContainerHigh">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-primary to-primaryContainer text-white flex items-center justify-center shadow-soft-sm shrink-0">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
              />
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
            Clinical Triage Model v2.4
          </Badge>
        </div>
      </div>

      {/* 2. Chat Scrollable Container */}
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
                  <div className="w-8 h-8 rounded-xl bg-error text-white flex items-center justify-center shrink-0 mt-1 shadow-soft-sm">
                    🚨
                  </div>
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
                      <p className="text-xs text-textSecondary leading-relaxed">
                        Symptoms such as sudden chest tightness, difficulty breathing, or severe sudden pain require immediate emergency evaluation.
                      </p>
                      <div className="pt-2 flex flex-wrap gap-2.5">
                        <a
                          href="tel:911"
                          className="inline-flex items-center gap-1.5 bg-error text-white text-xs font-bold px-4 py-2 rounded-pill hover:bg-[#a01616] shadow-soft transition-all"
                        >
                          📞 Call Emergency (911)
                        </a>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="bg-white border-error text-error hover:bg-errorContainer"
                          onClick={() => alert('Locating emergency rooms near you. Please call emergency services if this is urgent.')}
                        >
                          Find Nearest ER
                        </Button>
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
                          Log in to complete booking
                        </Button>
                      </Link>
                    </div>
                  )}

                  {/* Inline Doctor Option Cards (parsed from API response) */}
                  {msg.doctors && msg.doctors.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                      {msg.doctors.map((doc) => (
                        <div
                          key={doc.id}
                          className="p-4 bg-white rounded-2xl border border-surfaceContainerHigh shadow-soft hover:border-primary/40 transition-all flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <div className="flex items-center gap-2.5">
                                <div className={`w-9 h-9 rounded-xl ${doc.avatarBg} flex items-center justify-center font-bold text-xs shrink-0`}>
                                  {doc.name.split(' ')[1]?.charAt(0) || 'Dr'}
                                </div>
                                <div>
                                  <h4 className="font-heading font-bold text-xs text-textPrimary">
                                    {doc.name}
                                  </h4>
                                  <p className="text-[11px] text-textSecondary">{doc.specialization}</p>
                                </div>
                              </div>
                              {doc.fee && <span className="text-xs font-bold text-primary">{doc.fee}</span>}
                            </div>

                            <div className="text-[11px] text-textSecondary space-y-0.5 my-2">
                              {doc.clinic && <p className="truncate">📍 {doc.clinic}</p>}
                            </div>
                          </div>

                          {doc.slots.length > 0 && (
                            <div className="pt-2 border-t border-surfaceContainerHigh">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-textSecondary block mb-1.5">
                                Select Open Slot:
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {doc.slots.map((slot) => (
                                  <button
                                    key={`${doc.id}-${slot}`}
                                    type="button"
                                    onClick={() => handleSelectDoctorSlot(doc, slot)}
                                    disabled={isBotTyping}
                                    className="text-[11px] font-semibold bg-surfaceContainer hover:bg-primary hover:text-white text-textPrimary px-2.5 py-1 rounded-pill border border-surfaceContainerHigh transition-all disabled:opacity-50"
                                  >
                                    {slot}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Fallback option chips when doctor cards could not be parsed */}
                  {!msg.doctors?.length && msg.optionItems && msg.optionItems.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {msg.optionItems.map((option) => (
                        <button
                          key={option.option_id}
                          type="button"
                          onClick={() => handleOptionClick(option)}
                          disabled={isBotTyping}
                          className="text-xs font-semibold bg-surfaceContainer hover:bg-primary hover:text-white text-textPrimary px-3 py-1.5 rounded-pill border border-surfaceContainerHigh transition-all disabled:opacity-50"
                        >
                          {option.text}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Booking Confirmation Summary Card */}
                  {msg.bookingSummary && (
                    <div className="p-5 bg-white rounded-2xl border-2 border-primary/20 shadow-soft-md space-y-4 animate-fadeIn">
                      <div className="flex items-center justify-between border-b border-surfaceContainerHigh pb-3">
                        <div className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full bg-primary" />
                          <h4 className="font-heading font-bold text-sm text-textPrimary">
                            {msg.bookingSummary.isConfirmed
                              ? 'Booking Confirmed'
                              : 'Appointment Review'}
                          </h4>
                        </div>
                        <Badge
                          status={msg.bookingSummary.isConfirmed ? 'success' : 'pending'}
                          size="sm"
                        >
                          {msg.bookingSummary.isConfirmed ? 'Verified & Saved' : 'Pending Confirmation'}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-surfaceContainer rounded-xl">
                          <span className="text-[10px] text-textSecondary uppercase font-bold block">Doctor</span>
                          <span className="font-bold text-textPrimary text-sm">
                            {msg.bookingSummary.doctor.name}
                          </span>
                          {msg.bookingSummary.doctor.specialization && (
                            <p className="text-secondary text-[11px]">{msg.bookingSummary.doctor.specialization}</p>
                          )}
                        </div>

                        <div className="p-3 bg-surfaceContainer rounded-xl">
                          <span className="text-[10px] text-textSecondary uppercase font-bold block">Date & Time</span>
                          <span className="font-bold text-textPrimary text-sm">
                            {msg.bookingSummary.selectedSlot}
                          </span>
                        </div>

                        {(msg.bookingSummary.doctor.clinic || msg.bookingSummary.doctor.fee) && (
                          <div className="p-3 bg-surfaceContainer rounded-xl sm:col-span-2 flex items-center justify-between">
                            {msg.bookingSummary.doctor.clinic && (
                              <div>
                                <span className="text-[10px] text-textSecondary uppercase font-bold block">Location</span>
                                <span className="font-semibold text-textPrimary">
                                  {msg.bookingSummary.doctor.clinic}
                                  {msg.bookingSummary.doctor.address && ` (${msg.bookingSummary.doctor.address})`}
                                </span>
                              </div>
                            )}
                            {msg.bookingSummary.doctor.fee && (
                              <div className="text-right">
                                <span className="text-[10px] text-textSecondary uppercase font-bold block">Consultation Fee</span>
                                <span className="font-bold text-primary text-sm">{msg.bookingSummary.doctor.fee}</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      {!msg.bookingSummary.isConfirmed ? (
                        <div className="flex items-center gap-3 pt-2">
                          <Button
                            variant="primary"
                            size="md"
                            className="flex-1 justify-center"
                            isLoading={isBookingInProgress}
                            disabled={isBotTyping}
                            onClick={handleConfirmBooking}
                          >
                            {isBookingInProgress ? 'Reserving Appointment...' : 'Confirm Booking'}
                          </Button>
                          <Button
                            variant="secondary"
                            size="md"
                            disabled={isBotTyping}
                            onClick={handleChangeBooking}
                          >
                            Change
                          </Button>
                        </div>
                      ) : (
                        <div className="pt-2 flex flex-wrap gap-2.5">
                          <Link to="/dashboard">
                            <Button size="sm" variant="primary">
                              View in Dashboard &rarr;
                            </Button>
                          </Link>
                          <Link to="/appointments">
                            <Button size="sm" variant="secondary">
                              View All Appointments
                            </Button>
                          </Link>
                        </div>
                      )}
                    </div>
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
              <span>AI is analyzing clinical symptoms and doctor schedules...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Symptom Suggestion Chips */}
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

      {/* 5. Fixed Message Input Bar */}
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
          placeholder="Describe your symptoms (e.g., severe headache, persistent cough)..."
          className="flex-1 bg-transparent px-4 py-2 text-sm text-textPrimary placeholder:text-textSecondary/60 outline-none"
          disabled={isBotTyping}
        />

        <button
          type="submit"
          disabled={!inputVal.trim() || isBotTyping}
          className="w-10 h-10 rounded-pill bg-primary hover:bg-primaryContainer text-white flex items-center justify-center shrink-0 disabled:opacity-40 disabled:cursor-not-allowed shadow-soft-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="Send symptom message"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
          </svg>
        </button>
      </form>
    </div>
  );
};
