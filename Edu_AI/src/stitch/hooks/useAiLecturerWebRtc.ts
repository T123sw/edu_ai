import { useEffect, useRef, useState } from "react";

import { getAiLecturerOfferUrl } from "../api/video";
import type { AiLecturerOfferAnswer } from "../api/types";

type ConnectionStatus = "idle" | "connecting" | "connected" | "failed";

type UseAiLecturerWebRtcOptions = {
  autoStart?: boolean;
  offerParams?: Record<string, unknown>;
  onSessionId?: (sessionId: number) => void;
};

export function useAiLecturerWebRtc(options: UseAiLecturerWebRtcOptions = {}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const remoteStreamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [livetalkingSessionId, setLivetalkingSessionId] = useState<number | null>(null);

  const closeConnection = (nextStatus: ConnectionStatus = "idle") => {
    peerConnectionRef.current?.close();
    peerConnectionRef.current = null;
    remoteStreamRef.current?.getTracks().forEach((track) => track.stop());
    remoteStreamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }

    setStatus(nextStatus);
  };

  const start = async () => {
    if (peerConnectionRef.current) {
      return livetalkingSessionId;
    }

    setStatus("connecting");
    setError(null);

    const peerConnection = new RTCPeerConnection();
    const remoteStream = new MediaStream();
    peerConnectionRef.current = peerConnection;
    remoteStreamRef.current = remoteStream;

    if (videoRef.current) {
      videoRef.current.srcObject = remoteStream;
    }
    if (audioRef.current) {
      audioRef.current.srcObject = remoteStream;
    }

    peerConnection.addTransceiver("video", { direction: "recvonly" });
    peerConnection.addTransceiver("audio", { direction: "recvonly" });
    peerConnection.ontrack = (event) => {
      remoteStream.addTrack(event.track);
    };

    try {
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      const response = await fetch(getAiLecturerOfferUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...options.offerParams,
          sdp: offer.sdp,
          type: offer.type,
        }),
      });

      if (!response.ok) {
        throw new Error(`LiveTalking offer failed: ${response.status}`);
      }

      const answer = (await response.json()) as AiLecturerOfferAnswer;
      await peerConnection.setRemoteDescription({ sdp: answer.sdp, type: answer.type });
      setLivetalkingSessionId(answer.sessionid);
      options.onSessionId?.(answer.sessionid);
      setStatus("connected");
      return answer.sessionid;
    } catch (err) {
      closeConnection("failed");
      setError(err instanceof Error ? err.message : "LiveTalking connection failed");
      return null;
    }
  };

  const stop = () => {
    setLivetalkingSessionId(null);
    closeConnection("idle");
  };

  useEffect(() => {
    if (options.autoStart) {
      void start();
    }

    return () => {
      peerConnectionRef.current?.close();
      remoteStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return {
    audioRef,
    error,
    livetalkingSessionId,
    start,
    status,
    stop,
    videoRef,
  };
}
