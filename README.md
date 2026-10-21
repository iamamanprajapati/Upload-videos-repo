# Social Uploader

Ek baar video upload karo, aur wo **YouTube**, **Facebook Page** aur **Instagram (Reel)** teeno pe chala jayega. Ye poori tarah aapke Mac pe locally chalta hai. Saare logins/tokens bhi sirf aapke computer pe (`.env` aur `credentials/` mein) rehte hain.

## Chalana

```bash
cd ~/Documents/SocialMedia
./run.sh
```

Browser apne aap `http://127.0.0.1:5050` pe khul jayega. Pehli baar chalane pe ye zaroori packages install karega.

Jo platform abhi setup nahi hua, wo page pe grey dikhega aur bataega ki kya karna hai.

---

## Ek baar ka setup

### 1. YouTube (~10 min)

1. https://console.cloud.google.com pe jao, phir naya project banao (naam kuch bhi rakh lo).
2. **APIs & Services → Library** mein jao, **YouTube Data API v3** search karo aur **Enable** karo.
3. **APIs & Services → OAuth consent screen** (ya "Google Auth Platform") mein:
   - User type: **External**, app name aur apna email daalo
   - **Audience / Test users** mein apna Gmail add karo
   - Phir **Publish app** dabake status **In production** kar do. Ye zaroori hai, warna "Testing" mode mein login har 7 din mein expire ho jata hai. Verification ki zaroorat nahi hai, login ke waqt bas ek "unverified app" warning aayegi, wahan *Advanced → Continue* dabana.
4. **Credentials → Create Credentials → OAuth client ID** pe jao, type **Desktop app** chuno, phir JSON download karo.
5. Us file ko `credentials/client_secret.json` naam se save karo.
6. Ye command chalao:
   ```bash
   .venv/bin/python setup_youtube.py
   ```
   Browser khulega. Wahan apne channel wale account se **Allow** karo.

### 2. Facebook Page + Instagram (~15 min)

**Pehle ye check karo:**
- Aapke paas ek **Facebook Page** ho (personal profile pe API se post nahi hota).
- Instagram account **Professional** ho (Business ya Creator). Instagram app mein *Settings → Account type* se switch karo.
- Instagram us Facebook Page se **linked** ho (Page settings → Linked accounts → Instagram).

**Meta app banao:**
1. https://developers.facebook.com/apps pe jao aur **Create App** dabao.
2. Use cases mein ye dono chuno: **"Manage everything on your Page"** aur **"Manage messaging & content on Instagram"**. App "Development" mode mein hi rehne do. Aap khud app ke admin ho, isliye apne Page/Instagram ke liye App Review nahi chahiye.
3. **App settings → Basic** se **App ID** aur **App Secret** copy kar lo.

**Token lo:**
1. https://developers.facebook.com/tools/explorer kholo aur upar apna app select karo.
2. "User or Page" mein **User Token** chuno, phir ye permissions add karo:
   `pages_show_list, pages_read_engagement, pages_manage_posts, instagram_basic, instagram_content_publish, business_management`
3. **Generate Access Token** dabao. Login dialog mein apna **Page aur Instagram account select** karna mat bhoolna.
4. Token copy karo aur ye command chalao:
   ```bash
   .venv/bin/python setup_meta.py
   ```
   Ye App ID, Secret aur token maangega, phir apna Page chuno. Baaki sab `.env` mein apne aap save ho jayega.

---

## Dhyan rakhne wali baatein

| | |
|---|---|
| **YouTube: video Private ho jaata hai?** | Google ka rule hai ki *naye, unaudited* API projects se upload hue videos **private lock** ho jaate hain. Do raaste hain: (a) YouTube Studio mein jaake khud Public kar do, ya (b) Google ka free [API audit form](https://support.google.com/youtube/contact/yt_api_form) bhar do. Audit approve hone ke baad direct Public upload hoga. |
| **YouTube limit** | Free quota mein roz lagbhag **6 uploads** ho sakte hain. |
| **Instagram** | Hamesha **Reel** ke roop mein jata hai. Video 3 sec se 15 min ka ho, aur vertical 9:16 sabse achha dikhta hai. Roz max 50 posts. |
| **Facebook/Instagram login** | Meta ka login ~90 din chalta hai. Expire hone se 7 din pehle page pe warning aayegi. Tab Graph API Explorer se naya token lo aur `setup_meta.py` dobara chalao. |
| **Facebook "Reel"** | 3–90 sec, vertical video ke liye. Lambe video ke liye "Normal Video" mode chuno. |
| **Format** | MP4 (H.264 + AAC) best hai. MOV file apne aap MP4 mein convert ho jaati hai (`ffmpeg` se, quality same rehti hai). |
| **Purani files** | Upload ki hui files `uploads/` folder mein rehti hain. Jagah bachani ho to wahan se delete kar sakte ho. |

## Files

- `app.py`: local web server aur upload ka kaam
- `uploaders/`: har platform ka upload code (`youtube.py`, `facebook.py`, `instagram.py`)
- `setup_youtube.py`, `setup_meta.py`: ek baar ke login scripts
- `.env`, `credentials/`: aapke tokens (**inhe kisi ke saath share mat karna**)
# Upload-videos-repo
