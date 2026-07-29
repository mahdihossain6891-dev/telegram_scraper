import { ADDRESS_ENTITY_TYPES } from "./constants";
import type { EntityDisplayRow, MessageDisplayRow } from "./types";

export type AddressAlertCandidate = {
  chat_name: string;
  message_id: number;
  sender: string;
  text: string;
  categories: string[];
  keywords: string[];
  addresses: string[];
  alert_key: string;
  timestamp: string | null;
};

export function buildAddressAlertCandidates(
  messages: MessageDisplayRow[],
  entities: EntityDisplayRow[],
): AddressAlertCandidate[] {
  const entitiesByMessage = new Map<string, EntityDisplayRow[]>();

  for (const entity of entities) {
    if (!ADDRESS_ENTITY_TYPES.has(entity.entity_type)) {
      continue;
    }
    const key = `${entity.chat_id ?? ""}:${entity.message_id}`;
    const bucket = entitiesByMessage.get(key) || [];
    bucket.push(entity);
    entitiesByMessage.set(key, bucket);
  }

  const candidates: AddressAlertCandidate[] = [];
  for (const message of messages) {
    const key = `${message.chat_id}:${message.message_id}`;
    const hits = entitiesByMessage.get(key) || [];
    if (!hits.length) {
      continue;
    }
    const addresses = hits.map((row) => `${row.entity_type}: ${row.entity_value}`);
    candidates.push({
      chat_name: message.chat,
      message_id: message.message_id,
      sender: message.sender || "unknown",
      text: message.text || "",
      categories: message.categories
        ? message.categories.split(", ").map((part) => part.trim()).filter(Boolean)
        : [],
      keywords: message.keywords
        ? message.keywords.split(", ").map((part) => part.trim()).filter(Boolean)
        : [],
      addresses,
      alert_key: key,
      timestamp: message.timestamp || null,
    });
  }
  return candidates;
}
