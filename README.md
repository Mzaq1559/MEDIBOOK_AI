
---

## Testing

### Manual Verification (Aug 24, 2026)

✅ All 4 services running and healthy
✅ Frontend loads without errors
✅ Patient login works
✅ AI chat responds correctly
✅ Full booking flow tested end-to-end
✅ Admin dashboard shows real data
✅ Role-based routing verified
✅ Database has fresh test data

### Backend Tests

```bash
docker compose exec backend pytest -v
```

### AI Service Tests

```bash
docker compose exec ai-service pytest -v
```

---

## Known Limitations

### Current MVP

- Web-first (no native mobile app)
- English-primary chat
- In-memory AI sessions (reset on service restart)

### In Development

- Google Calendar sync (API integration)
- Email reminders (SMTP setup)
- n8n workflows (orchestration)

### Post-Hackathon

- WhatsApp Business API
- Prescription management endpoints
- Persistent chat database
- Urdu/English bilingual UI
- Native iOS/Android apps

---

## Team

Built in 6 days (Aug 22–24) by a 4-person team for Alibaba Cloud AI Hackathon Pakistan 2026.

Extended deadline to Sept 4, 2026 allows proper implementation of integrations without compromising code quality.

---

## License

No open-source license. Submitted for Alibaba Cloud AI Hackathon Pakistan 2026 evaluation.
