import { GoogleGenAI } from "@google/genai";
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
async function run() {
  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: "What good Italian restaurants are nearby San Francisco?",
      config: {
        tools: [{googleSearch: {}}],
      },
    });
    console.log(response.text);
  } catch (e) {
    console.error(e);
  }
}
run();
