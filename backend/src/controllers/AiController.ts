import { Request, Response } from 'express';
import OpenAI from 'openai';

type PersonaReference = {
    name: string;
    image_base64?: string;
    image?: string;
};

const PERSONA_MENTION_REGEX = /@([a-z0-9][a-z0-9._-]{0,30})/gi;

const normalizeName = (name: string) => name.trim().toLowerCase();

const stripDataUrlPrefix = (value: string) =>
    value.replace(/^data:image\/[a-z0-9.+-]+;base64,/i, '');

const resolvePersonaMentions = (prompt: string, personas: PersonaReference[]) => {
    const personaByName = new Map<string, PersonaReference>();
    personas.forEach((persona) => {
        const normalized = normalizeName(persona.name);
        if (!normalized || personaByName.has(normalized)) return;
        personaByName.set(normalized, persona);
    });

    const uniqueMentions = new Set<string>();
    PERSONA_MENTION_REGEX.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = PERSONA_MENTION_REGEX.exec(prompt)) !== null) {
        uniqueMentions.add(match[1]);
    }

    const resolvedMentions = new Map<string, string>();
    const resolvedPersonas: PersonaReference[] = [];

    uniqueMentions.forEach((mention) => {
        const normalizedMention = normalizeName(mention);
        if (!normalizedMention) return;

        const exact = personaByName.get(normalizedMention);
        if (!exact) return;
        resolvedMentions.set(mention, exact.name);
        resolvedPersonas.push(exact);
    });

    PERSONA_MENTION_REGEX.lastIndex = 0;
    const promptWithResolvedMentions = prompt.replace(PERSONA_MENTION_REGEX, (fullMatch, name) => {
        const resolvedName = resolvedMentions.get(name);
        return resolvedName ? resolvedName : fullMatch;
    });

    const uniquePersonas = new Map<string, PersonaReference>();
    resolvedPersonas.forEach((persona) => {
        const normalized = normalizeName(persona.name);
        if (uniquePersonas.has(normalized)) return;
        uniquePersonas.set(normalized, persona);
    });

    const personaNames = Array.from(uniquePersonas.values()).map((persona) => persona.name);
    const referenceImages = Array.from(uniquePersonas.values())
        .map((persona) => persona.image_base64 ?? persona.image)
        .filter((image): image is string => Boolean(image))
        .map((image) => ({ b64: stripDataUrlPrefix(image) }));

    return {
        prompt: promptWithResolvedMentions,
        personaNames,
        referenceImages
    };
};

const THERMAL_SYSTEM_PROMPT = `You are a designer for a thermal receipt printer used for intimate family notes.

Your job is to create PRINT-READY artwork and layouts that will be printed on a black-and-white thermal printer.

CRITICAL CONSTRAINTS:
- Output must be black and white only (no grayscale, no color).
- Maximum width is exactly 576 pixels.
- Height can vary but should be as compact as possible.
- Background must be white.
- Artwork must print clearly on thermal paper:
  - Use bold lines
  - Avoid fine details
  - Avoid large dark filled areas
- Favor simple line art, icons, doodles, and high-contrast typography.

STYLE GUIDELINES:
- Warm, gentle, hand-made, human.
- Suitable for children and family.
- Never creepy, scary, or overly realistic.
- Think: refrigerator note, lunchbox drawing, bedtime doodle.
- Slight imperfections are good.

CONTENT GUIDELINES:
- Assume the sender is a father.
- The recipient may be a child or partner.
- Tone should feel loving, reassuring, and calm.
- Avoid sarcasm or irony.

OUTPUT FORMAT:
Return a single JSON object with:
- "image_prompt": a concise internal description of the image to generate
- "layout_description": how text and image are arranged vertically
- "suggested_caption" (optional): short text to include
- "style_tags": list of tags like ["line_art", "doodle", "bedtime"]
- "generation_instructions": explicit instructions to constrain the image generator

DO NOT mention printers, pixels, or technical details in the image content itself.
DO NOT include any explanatory text outside the JSON.`;

export class AiController {
    static async generateDesign(req: Request, res: Response) {
        try {
            const { prompt, personas } = req.body as {
                prompt?: string;
                personas?: PersonaReference[];
            };
            if (!prompt) {
                res.status(400).json({ error: 'Prompt is required' });
                return;
            }

            if (!process.env.OPENAI_API_KEY) {
                console.error('[AI] Missing OPENAI_API_KEY');
                res.status(503).json({ error: 'AI service not configured (Missing API Key)' });
                return;
            }

            const openai = new OpenAI();

            const resolved = resolvePersonaMentions(prompt, personas ?? []);
            console.log('[AI] Refining prompt:', resolved.prompt);

            // 1. Refine Prompt with GPT-4o (or 3.5-turbo)
            const completion = await openai.chat.completions.create({
                model: "gpt-4o",
                messages: [
                    { role: "system", content: THERMAL_SYSTEM_PROMPT },
                    {
                        role: "user",
                        content: [
                            `User wants to create the following message: "${resolved.prompt}"`,
                            resolved.personaNames.length
                                ? `The message includes people tagged as ${resolved.personaNames.join(', ')}. Use these names (without @) in the image description and keep the tone family-friendly.`
                                : null
                        ].filter(Boolean).join(' ')
                    }
                ],
                response_format: { type: "json_object" }
            });

            let designSpecs;
            try {
                const content = completion.choices[0].message.content || '{}';
                designSpecs = JSON.parse(content);
            } catch (e) {
                console.error('[AI] Failed to parse design specs:', completion.choices[0].message.content);
                throw new Error('AI returned invalid design specifications');
            }

            console.log('[AI] Design Specs:', designSpecs);

            // 2. Generate Image with GPT Image 1.5 (latest model, replaces DALL-E 3)
            // We ask for a simple black and white line art style explicitly in the prompt
            const personaInstruction = resolved.personaNames.length
                ? `Use the provided reference images to depict ${resolved.personaNames.join(', ')} accurately.`
                : '';
            const imagePrompt = `Black and white thermal printer line art. Simple, bold lines. No shading. No grayscale. White background. ${designSpecs.image_prompt}. ${designSpecs.generation_instructions} ${personaInstruction}`.trim();

            console.log('[AI] Generating image with gpt-image-1.5...');
            console.log('[AI] Prompt:', imagePrompt);
            console.log('[AI] Reference Images:', resolved.referenceImages.length);

            const imageResponse = (await openai.images.generate({
                model: "gpt-image-1.5",
                prompt: imagePrompt,
                n: 1,
                size: "1024x1024",
                quality: "low",
                output_format: "png",
                response_format: "b64_json",
                ...(resolved.referenceImages.length ? { images: resolved.referenceImages } : {})
            } as any)) as any;

            if (!imageResponse.data || !imageResponse.data[0]) {
                console.error('[AI] No image data in response:', JSON.stringify(imageResponse));
                throw new Error('No image data returned from OpenAI');
            }

            const rawBase64 = imageResponse.data[0].b64_json;
            if (!rawBase64) {
                console.error('[AI] Missing b64_json in response data:', JSON.stringify(imageResponse.data[0]));
                throw new Error('Image data was not returned in base64 format');
            }

            res.json({
                image: `data:image/png;base64,${rawBase64}`, // High-res, frontend will resize
                caption: designSpecs.suggested_caption,
                specs: designSpecs
            });

        } catch (error: any) {
            console.error('[AI] Generation failed:', error);

            // Extract more details if available
            const errorMessage = error.response?.data?.error?.message || error.message || 'AI generation failed';
            const errorStatus = error.response?.status || 500;

            res.status(errorStatus).json({
                error: errorMessage,
                details: error.response?.data || error.data || null
            });
        }
    }
}
