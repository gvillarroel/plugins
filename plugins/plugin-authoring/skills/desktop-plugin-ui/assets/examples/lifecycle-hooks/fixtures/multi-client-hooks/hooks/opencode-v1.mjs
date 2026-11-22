import recorder from "./record.cjs";

export const MultiClientHooks = async () => ({
  async event({ event }) {
    if (event.type === "session.created") {
      recorder.record("opencode:session.created");
    }
  },
});
