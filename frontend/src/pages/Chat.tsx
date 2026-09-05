import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge, LoadingSpinner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import {
  sendChatMessage,
  sendChatMessageStream,
  formatChatTimestamp,
  getChatErrorMessage,
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

function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/__(.+?)__/gs, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*/g, '')
    .replace(/__/g, '')
    .trim();
}

function listsAppointmentDetails(text?: string): boolean {
  if (!text) return false;
  const cleaned = stripMarkdown(text).toLowerCase();
  const hasDoctor = /\bdoctor\s*:/.test(cleaned);
  const hasWhen = /\b(date|time|date\s*&\s*time)\s*:/.test(cleaned);
  const hasClinic = /\bclinic\s*:/.test(cleaned);
  const hasReason = /\breason(\s+noted)?\s*:/.test(cleaned);
  return hasDoctor && (hasWhen || hasClinic || hasReason);
}

function mapApiResponseToBotMessage(
  response: Awaited<ReturnType<typeof sendChatMessage>>
): Omit<ChatMessage, 'id' | 'sender'> {
  const isEmergency = response.next_action === 'emergency_redirect';
  const requiresLogin = response.next_action === 'waiting_for_login';
  const text = response.bot_message ? stripMarkdown(response.bot_message) : response.bot_message;
  const uiData = response.ui_data ? { ...response.ui_data } : response.ui_data;
  const isBookingAction = [
    'waiting_for_doctor_selection',
    'waiting_for_slot_selection',
    'waiting_for_confirm',
    'waiting_for_reschedule_confirm',
    'waiting_for_cancel_confirm'
  ].includes(response.next_action || '');

  if (response.next_action === 'waiting_for_slot_selection' && uiData) {
    delete uiData.doctors;
  }

  if (listsAppointmentDetails(text) && uiData && !isBookingAction) {
    delete uiData.appointments;
    delete uiData.doctors;
  }

  return {
    text,
    timestamp: formatChatTimestamp(response.timestamp),
    isEmergency,
    requiresLogin,
    optionItems: response.options.length > 0 ? response.options : undefined,
    uiData,
    nextAction: response.next_action,
  };
}

export const Chat: React.FC = () => {
  const { currentUser } = useAuth();
  const rawName = (currentUser?.name || '').trim();
  let userName = 'there';
  if (rawName.includes(',')) {
    userName = rawName.split(',')[1]?.trim().split(/\s+/)[0] || rawName.split(',')[0].split(/\s+/)[0] || 'there';
  } else if (rawName) {
    userName = rawName.split(/\s+/)[0];
  }

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-welcome',
      sender: 'bot',
      text: `Hi ${userName}! How can I help you today?`,
      timestamp: 'Just now',
    },
  ]);

  const [inputVal, setInputVal] = useState('');
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [currentStatusLabel, setCurrentStatusLabel] = useState<string | null>(null);
  const [isBookingInProgress, setIsBookingInProgress] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const [language, setLanguage] = useState<'en' | 'ur'>(() => {
    return (localStorage.getItem('preferredLanguage') as 'en' | 'ur') || 'en';
  });
  const [isRecording, setIsRecording] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState('⚪ Idle');
  const recognitionRef = useRef<any>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  let patientId: string | null = null;
  if (currentUser?.userType === 'patient') {
    if (currentUser.patientId) {
      patientId = currentUser.patientId;
    } else if (currentUser.id) {
      console.warn('[Chat] currentUser.patientId is missing on patient user profile. Falling back to currentUser.id (users.id).');
      patientId = currentUser.id;
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isBotTyping]);

  const toggleLanguage = useCallback(() => {
    const newLang = language === 'en' ? 'ur' : 'en';
    setLanguage(newLang);
    localStorage.setItem('preferredLanguage', newLang);
    setVoiceStatus(`Language: ${newLang === 'en' ? 'English' : 'Urdu'}`);
  }, [language]);

  const startVoiceInput = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Your browser doesn\'t support voice input. Please use Chrome or Edge.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = language === 'en' ? 'en-US' : 'ur-PK';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognitionRef.current = recognition;

    setIsRecording(true);
    setVoiceStatus('🎤 Listening...');

    recognition.start();

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      setInputVal(transcript);
      setVoiceStatus(`✅ Heard: "${transcript}"`);
      
      setTimeout(() => {
        if (transcript.trim()) {
          handleSendMessage(transcript);
        }
      }, 500);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      let errorMsg = '⚠️ Could not understand. ';
      if (event.error === 'not-allowed') {
        errorMsg += 'Please allow microphone access.';
      } else if (event.error === 'no-speech') {
        errorMsg += 'No speech detected. Please try again.';
      } else if (event.error === 'audio-capture') {
        errorMsg += 'No microphone found. Please check your mic.';
      } else {
        errorMsg += 'Please try again.';
      }
      
      setVoiceStatus(errorMsg);
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
      if (!inputVal) {
        setVoiceStatus('⏹ Stopped listening');
      }
    };
  }, [language, inputVal]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === ' ' && target?.tagName !== 'INPUT' && target?.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (!isRecording && !isBotTyping) {
          startVoiceInput();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isRecording, isBotTyping, startVoiceInput]);

  const quickSymptoms = [
    'Book an appointment',
    'Cancel my appointment',
    'Reschedule appointment',
    'What are my appointments?',
  ];

  const callChatApi = useCallback(
    async (text: string, optionId?: string) => {
      const isConfirmMessage = /^(yes|confirm|yes,\s*confirm)/i.test(text.trim());

      setIsBotTyping(true);
      setCurrentStatusLabel(null);
      if (isConfirmMessage) {
        setIsBookingInProgress(true);
      }

      try {
        const messagePayload = optionId ? `${text} ${optionId}` : text;
        const response = await sendChatMessageStream({
          message: messagePayload,
          conversation_id: conversationId,
          patient_id: patientId,
          onStatus: (label) => {
            setCurrentStatusLabel(label);
          },
        });

        setConversationId(response.conversation_id);

        const botMessage: ChatMessage = {
          id: `bot-${Date.now()}`,
          sender: 'bot',
          ...mapApiResponseToBotMessage(response),
        };

        setMessages((prev) => [...prev, botMessage]);
      } catch (error: any) {
        console.error('[Chat] Caught chat API error:', error);
        setMessages((prev) => [
          ...prev,
          {
            id: `bot-error-${Date.now()}`,
            sender: 'bot',
            text: error?.message || getChatErrorMessage(error),
            timestamp: formatChatTimestamp(),
          },
        ]);
      } finally {
        setIsBotTyping(false);
        setCurrentStatusLabel(null);
        setIsBookingInProgress(false);
        setVoiceStatus('⚪ Idle');
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
            RAG Clinical Triage
          </Badge>
        </div>
      </div>

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
                        <a href="tel:911" className="inline-flex items-center gap-1.5 bg-error text-white text-xs font-bold px-4 py-2 rounded-pill hover:bg-[#a01616] shadow-soft transition-all">
                          📞 Call Emergency (911)
                        </a>
                      </div>
                    </div>
                    <span className="text-[10px] text-textSecondary mt-1 px-1 block">{msg.timestamp}</span>
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="flex justify-start items-start gap-3 animate-fadeIn">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-primaryContainer text-white flex items-center justify-center shrink-0 mt-1 shadow-soft-sm text-xs font-bold">
                  AI
                </div>

                <div className="w-full max-w-2xl space-y-3">
                  {msg.text && (
                    <div className="bg-gradient-to-br from-[#EFF4FF] to-[#E6EEFF] border border-primaryContainer/15 p-4 rounded-2xl rounded-tl-sm text-textPrimary text-sm leading-relaxed shadow-soft-sm whitespace-pre-line">
                      {msg.text}
                    </div>
                  )}

                  {msg.requiresLogin && (
                    <div className="pt-1">
                      <Link to="/login">
                        <Button size="sm" variant="primary">
                          Log in to continue
                        </Button>
                      </Link>
                    </div>
                  )}

                  {msg.nextAction === 'waiting_for_doctor_selection' &&
                    msg.uiData?.doctors &&
                    msg.uiData.doctors.length > 0 &&
                    !listsAppointmentDetails(msg.text) && (() => {
                      const recommendedSpecialty = msg.uiData.triage?.specialty;
                      const recommendedDoctors = recommendedSpecialty
                        ? msg.uiData.doctors.filter(
                            (doc) => doc.specialization.toLowerCase() === recommendedSpecialty.toLowerCase()
                          )
                        : msg.uiData.doctors;

                      return (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                          {recommendedDoctors.map((doc) => (
                            <DoctorCard
                              key={doc.doctor_id}
                              doctor={doc}
                              onClick={(id) => handleAction("Selected Doctor", id)}
                              disabled={isBotTyping}
                            />
                          ))}
                        </div>
                      );
                    })()}

                  {msg.nextAction === 'waiting_for_slot_selection' &&
                    msg.uiData?.slots &&
                    msg.uiData.slots.length > 0 &&
                    !listsAppointmentDetails(msg.text) && (
                      <div className="pt-2">
                        <TimeSlotGrid
                          slots={msg.uiData.slots}
                          onSelect={(ts) => handleAction("Selected Time Slot", ts)}
                          disabled={isBotTyping}
                        />
                      </div>
                    )}

                  {msg.uiData?.appointments &&
                    msg.uiData.appointments.length > 0 &&
                    msg.nextAction === 'show_appointments' && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                        {msg.uiData.appointments.map((appt) => (
                          <AppointmentCard
                            key={appt.appointment_id}
                            appointment={appt}
                            onSelect={undefined}
                            disabled={isBotTyping}
                          />
                        ))}
                      </div>
                    )}

                  {msg.uiData?.booking &&
                    (msg.nextAction === 'waiting_for_confirm' ||
                      (msg.uiData.booking.status &&
                        msg.uiData.booking.status !== 'pending')) && (
                    <ConfirmationCard
                      booking={msg.uiData.booking}
                      isLoading={isBookingInProgress}
                      disabled={isBotTyping}
                      onConfirm={() => handleAction('yes, confirm')}
                      onChange={() => handleAction('change')}
                    />
                  )}

                  {msg.uiData?.reschedule &&
                    (msg.nextAction === 'waiting_for_reschedule_confirm' ||
                      (msg.uiData.reschedule.status &&
                        msg.uiData.reschedule.status !== 'pending')) && (
                    <RescheduleConfirmation
                      reschedule={msg.uiData.reschedule}
                      isLoading={isBookingInProgress}
                      disabled={isBotTyping}
                      onConfirm={() => handleAction('yes, confirm')}
                      onChange={() => handleAction('change')}
                    />
                  )}

                  {msg.uiData?.triage?.rag_used && (msg.uiData.triage.sources?.length ?? 0) > 0 && (
                    <div className="bg-surfaceContainer/60 border border-surfaceContainerHigh rounded-xl p-4 text-xs text-textSecondary space-y-2">
                      <p className="font-semibold text-textPrimary">Based on medical knowledge</p>
                      <ul className="list-disc pl-4 space-y-1">
                        {msg.uiData.triage.sources!.map((source) => (
                          <li key={source.id}>{source.title}</li>
                        ))}
                      </ul>
                      <p>
                        This information is for general guidance and does not replace professional medical evaluation.
                      </p>
                    </div>
                  )}

                  <span className="text-[10px] text-textSecondary mt-1 px-1 block">{msg.timestamp}</span>
                </div>
              </div>
            );
          })}

          {isBotTyping && (
            <div className="flex items-center gap-2.5 text-xs text-textSecondary animate-fadeIn pl-2">
              <LoadingSpinner size="sm" color="primary" />
              <span className="transition-all duration-200 font-medium text-textPrimary">
                {currentStatusLabel || 'AI is thinking...'}
              </span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

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

      <div className="space-y-2">
        <div className="flex items-center gap-2 px-1">
          <button
            type="button"
            onClick={toggleLanguage}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-primary/20 ${
              language === 'en'
                ? 'bg-primary text-white hover:bg-primary/90'
                : 'bg-orange-500 text-white hover:bg-orange-600'
            }`}
          >
            {language === 'en' ? '🇬🇧 English' : '🇵🇰 اردو'}
          </button>

          <button
            type="button"
            onClick={startVoiceInput}
            disabled={isRecording || isBotTyping}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-primary/20 ${
              isRecording
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-surfaceContainer hover:bg-surfaceContainerHigh text-textPrimary'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isRecording ? '🔴 Recording...' : '🎤 Speak'}
          </button>

          <span className="text-xs text-textSecondary/70 italic ml-auto">
            {voiceStatus}
          </span>
        </div>

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
            placeholder={language === 'en' ? "Type or speak your message..." : "اپنا پیغام ٹائپ کریں یا بولیں..."}
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

        <div className="text-center text-[10px] text-textSecondary/50">
          Press <kbd className="px-1.5 py-0.5 bg-surfaceContainer rounded text-xs font-mono">Space</kbd> to start voice input
        </div>
      </div>
    </div>
  );
};