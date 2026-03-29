import { GoogleGenAI } from "@google/genai";
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
async function run() {
  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: "What good Italian restaurants are nearby?",
      config: {
        tools: [{googleMaps: {}}],
        toolConfig: {
          retrievalConfig: {
            latLng: {
              latitude: 37.78193,
              longitude: -122.40476
            }
          }
        }
      },
    });
    console.log(response.text);
  } catch (e) {
    console.error(e);
  }
}
run();
