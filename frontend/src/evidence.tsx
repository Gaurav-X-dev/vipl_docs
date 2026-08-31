import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Camera,
  CircleCheck,
  MapPin,
  RefreshCw,
  SwitchCamera,
  TriangleAlert,
  UploadCloud,
  X,
} from "lucide-react";
import { api, errorMessage } from "./api";
import { Field, Modal, SelectInput, TextInput, useToast } from "./ui";
import { DOCUMENT_CATEGORIES, asOptions } from "./types";

type Source = "camera" | "file";

/**
 * Evidence capture for a field visit.
 *
 * An investigator standing outside a house should not have to take a photo in
 * one app, find it in another, then type in coordinates. So the camera is the
 * first thing this offers, the location is fetched the moment the dialog opens,
 * and both are stamped onto the upload without anyone being asked to remember.
 *
 * Uploading a file that already exists stays one click away, because office
 * staff attach scans and PDFs from a desk.
 */
export function EvidenceDialog({
  open,
  caseId,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();

  const [source, setSource] = useState<Source>("camera");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [category, setCategory] = useState("PHOTOGRAPH");
  const [description, setDescription] = useState("");

  const fileRef = useRef<HTMLInputElement>(null);

  const location = useGeolocation(open);
  const camera = useCamera(open && source === "camera" && !file);

  // Revoke the object URL when the picture changes, or the tab leaks memory
  // over a long shift of uploads.
  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const reset = useCallback(() => {
    setFile(null);
    setDescription("");
    setSource("camera");
  }, []);

  const upload = useMutation({
    mutationFn: () => {
      const data = new FormData();
      data.append("file", file as File);
      data.append("category", category);
      if (description) data.append("description", description);
      if (location.latitude !== null) {
        data.append("geo_latitude", location.latitude.toFixed(6));
        data.append("geo_longitude", (location.longitude as number).toFixed(6));
      }
      return api.post(`/cases/${caseId}/documents`, data);
    },
    onSuccess: () => {
      toast.success(
        location.latitude !== null
          ? "Evidence uploaded with its location."
          : "Evidence uploaded.",
      );
      client.invalidateQueries({ queryKey: ["case-documents", caseId] });
      onDone();
      reset();
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  async function takePhoto() {
    const shot = await camera.capture();
    if (shot) setFile(shot);
  }

  function close() {
    reset();
    onClose();
  }

  return (
    <Modal
      open={open}
      title="Add evidence"
      subtitle="Take a photo on the spot, or attach a file. The location is recorded with it."
      onClose={close}
      footer={
        <>
          <button className="secondary" onClick={close}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => upload.mutate()}
            disabled={upload.isPending || !file}
          >
            <UploadCloud />
            {upload.isPending ? "Uploading…" : "Upload"}
          </button>
        </>
      }
    >
      <div className="capture-switch" role="tablist">
        <button
          role="tab"
          aria-selected={source === "camera"}
          className={source === "camera" ? "active" : ""}
          onClick={() => {
            setSource("camera");
            setFile(null);
          }}
        >
          <Camera /> Take a photo
        </button>
        <button
          role="tab"
          aria-selected={source === "file"}
          className={source === "file" ? "active" : ""}
          onClick={() => {
            setSource("file");
            setFile(null);
          }}
        >
          <UploadCloud /> Choose a file
        </button>
      </div>

      {file ? (
        <div className="capture-stage">
          {preview ? (
            <img src={preview} alt="The evidence about to be uploaded" />
          ) : (
            <div className="capture-file">
              <UploadCloud />
              <b>{file.name}</b>
              <small>{(file.size / 1024).toFixed(0)} KB</small>
            </div>
          )}
          <button className="capture-clear" onClick={() => setFile(null)}>
            <X /> Retake
          </button>
        </div>
      ) : source === "camera" ? (
        <div className="capture-stage">
          {camera.error ? (
            <div className="capture-error">
              <TriangleAlert />
              <b>{camera.error}</b>
              <span>
                Allow camera access in the browser, or switch to Choose a file.
              </span>
              <button className="secondary" onClick={camera.retry}>
                <RefreshCw /> Try again
              </button>
            </div>
          ) : (
            <>
              {/* A live viewfinder carries no audio track to caption. */}
              <video ref={camera.videoRef} autoPlay playsInline muted />
              {!camera.ready && <div className="capture-hint">Starting the camera…</div>}
            </>
          )}
          <div className="capture-actions">
            <button
              className="shutter"
              onClick={takePhoto}
              disabled={!camera.ready}
              aria-label="Take the photo"
            >
              <Camera />
            </button>
            {camera.canSwitch && (
              <button
                className="secondary"
                onClick={camera.flip}
                disabled={!camera.ready}
              >
                <SwitchCamera /> Flip
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="capture-stage">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx"
            hidden
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className="file-drop"
            onClick={() => fileRef.current?.click()}
          >
            <UploadCloud />
            <b>Choose a file</b>
            <small>PDF, JPG, PNG, WEBP, DOCX or XLSX</small>
          </button>
        </div>
      )}

      <div className={location.latitude !== null ? "geo-strip found" : "geo-strip"}>
        <MapPin />
        <span>
          {location.error ? (
            <>
              <b>No location</b>
              <small>{location.error}</small>
            </>
          ) : location.latitude === null ? (
            <>
              <b>Finding your location…</b>
              <small>The photo is stamped with it automatically.</small>
            </>
          ) : (
            <>
              <b>
                {location.latitude.toFixed(5)}, {location.longitude?.toFixed(5)}
              </b>
              <small>
                Accurate to about {Math.round(location.accuracy ?? 0)} m
              </small>
            </>
          )}
        </span>
        {location.latitude !== null ? (
          <CircleCheck className="geo-ok" />
        ) : (
          <button className="text-link" onClick={location.retry}>
            Retry
          </button>
        )}
      </div>

      <Field label="Category">
        <SelectInput
          value={category}
          onChange={setCategory}
          options={asOptions(DOCUMENT_CATEGORIES)}
          allowEmpty={false}
        />
      </Field>
      <Field label="Description" hint="What does this show? Optional.">
        <TextInput
          value={description}
          onChange={setDescription}
          placeholder="e.g. Front of the residence, name plate visible"
        />
      </Field>
    </Modal>
  );
}

/** Live camera, with the front/back switch phones need. */
function useCamera(active: boolean) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [attempt, setAttempt] = useState(0);
  const [canSwitch, setCanSwitch] = useState(false);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setReady(false);
  }, []);

  useEffect(() => {
    if (!active) {
      stop();
      return;
    }
    let cancelled = false;

    (async () => {
      setError(null);
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("This browser cannot open a camera.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setReady(true);
        const cameras = await navigator.mediaDevices.enumerateDevices();
        setCanSwitch(
          cameras.filter((device) => device.kind === "videoinput").length > 1,
        );
      } catch (failure) {
        if (cancelled) return;
        const name = (failure as DOMException)?.name;
        setError(
          name === "NotAllowedError"
            ? "Camera permission was refused."
            : name === "NotFoundError"
              ? "No camera was found on this device."
              : "The camera could not be opened.",
        );
      }
    })();

    return () => {
      cancelled = true;
      stop();
    };
  }, [active, facing, attempt, stop]);

  const capture = useCallback(async (): Promise<File | null> => {
    const video = videoRef.current;
    if (!video || !ready) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) return null;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.92),
    );
    if (!blob) return null;
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    return new File([blob], `visit-photo-${stamp}.jpg`, { type: "image/jpeg" });
  }, [ready]);

  return {
    videoRef,
    ready,
    error,
    canSwitch,
    capture,
    flip: () => setFacing((f) => (f === "environment" ? "user" : "environment")),
    retry: () => setAttempt((n) => n + 1),
  };
}

/** Ask for the location as soon as the dialog opens, not when Upload is pressed. */
function useGeolocation(active: boolean) {
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [accuracy, setAccuracy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!active) return;
    setError(null);
    if (!navigator.geolocation) {
      setError("This browser cannot provide a location.");
      return;
    }
    let cancelled = false;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (cancelled) return;
        setLatitude(position.coords.latitude);
        setLongitude(position.coords.longitude);
        setAccuracy(position.coords.accuracy);
      },
      (failure) => {
        if (cancelled) return;
        setError(
          failure.code === failure.PERMISSION_DENIED
            ? "Location permission was refused."
            : "Your location could not be read.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
    );
    return () => {
      cancelled = true;
    };
  }, [active, attempt]);

  return {
    latitude,
    longitude,
    accuracy,
    error,
    retry: () => setAttempt((n) => n + 1),
  };
}

/* --------------------------------------------------------------- Bulk photos */

type QueueState = "waiting" | "uploading" | "done" | "failed";

type Queued = {
  id: string;
  file: File;
  preview: string;
  state: QueueState;
  error?: string;
};

/**
 * Several photographs at once, from the case overview.
 *
 * An investigator comes back from a visit with a handful of pictures of the
 * house, the name plate and the family. Adding them one dialog at a time was
 * the slowest thing in the app, so this takes the whole set in one go, stamps
 * every one with the location read once at the start, and reports each file
 * separately — one rejected photo must not discard the other nine.
 *
 * Uploads run one after another rather than all at once: a phone on a village
 * connection handles a queue far better than ten parallel requests.
 */
export function PhotoUploadPanel({
  caseId,
  onDone,
}: {
  caseId: string;
  onDone?: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [queue, setQueue] = useState<Queued[]>([]);
  const [busy, setBusy] = useState(false);
  const location = useGeolocation(true);

  // Object URLs are revoked when the item leaves the queue, not on every
  // render, or a long queue leaks a preview per keystroke elsewhere.
  useEffect(
    () => () => {
      queue.forEach((item) => URL.revokeObjectURL(item.preview));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  function add(files: FileList | null) {
    if (!files?.length) return;
    const picked = Array.from(files).filter((f) => f.type.startsWith("image/"));
    const rejected = files.length - picked.length;
    if (rejected > 0) {
      toast.error(
        `${rejected} file${rejected > 1 ? "s were" : " was"} not an image and ${
          rejected > 1 ? "were" : "was"
        } skipped.`,
      );
    }
    setQueue((current) => [
      ...current,
      ...picked.map((file) => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
        file,
        preview: URL.createObjectURL(file),
        state: "waiting" as QueueState,
      })),
    ]);
  }

  function remove(id: string) {
    setQueue((current) => {
      const going = current.find((item) => item.id === id);
      if (going) URL.revokeObjectURL(going.preview);
      return current.filter((item) => item.id !== id);
    });
  }

  async function uploadAll() {
    const pending = queue.filter((item) => item.state !== "done");
    if (!pending.length) return;
    setBusy(true);
    let uploaded = 0;

    for (const item of pending) {
      setQueue((current) =>
        current.map((q) => (q.id === item.id ? { ...q, state: "uploading" } : q)),
      );
      try {
        const data = new FormData();
        data.append("file", item.file);
        data.append("category", "PHOTOGRAPH");
        if (location.latitude !== null && location.longitude !== null) {
          data.append("geo_latitude", location.latitude.toFixed(6));
          data.append("geo_longitude", location.longitude.toFixed(6));
        }
        await api.post(`/cases/${caseId}/documents`, data);
        uploaded += 1;
        setQueue((current) =>
          current.map((q) => (q.id === item.id ? { ...q, state: "done" } : q)),
        );
      } catch (failure) {
        setQueue((current) =>
          current.map((q) =>
            q.id === item.id
              ? { ...q, state: "failed", error: errorMessage(failure) }
              : q,
          ),
        );
      }
    }

    setBusy(false);
    if (uploaded > 0) {
      client.invalidateQueries({ queryKey: ["case-documents", caseId] });
      toast.success(
        `${uploaded} photograph${uploaded > 1 ? "s" : ""} uploaded${
          location.latitude !== null ? " with location" : ""
        }.`,
      );
      onDone?.();
    }
    const failed = queue.length - uploaded;
    if (failed > 0 && uploaded === 0) {
      toast.error("None of the photographs could be uploaded.");
    }
  }

  const waiting = queue.filter((item) => item.state !== "done").length;

  return (
    <div className="photo-panel">
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(event) => {
          add(event.target.files);
          // Reset, so picking the same file twice still fires a change.
          event.target.value = "";
        }}
      />

      <div className="photo-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
        >
          <UploadCloud /> Add photographs
        </button>
        {waiting > 0 && (
          <button
            type="button"
            className="primary"
            onClick={uploadAll}
            disabled={busy}
          >
            {busy ? "Uploading…" : `Upload ${waiting}`}
          </button>
        )}
      </div>

      <p className={location.latitude !== null ? "photo-geo found" : "photo-geo"}>
        <MapPin />
        {location.error
          ? `No location — ${location.error}`
          : location.latitude === null
            ? "Finding your location…"
            : `Stamped at ${location.latitude.toFixed(5)}, ${location.longitude?.toFixed(5)}`}
      </p>

      {queue.length === 0 ? (
        <p className="muted">
          Choose several at once. Each is stamped with the location above.
        </p>
      ) : (
        <ul className="photo-queue">
          {queue.map((item) => (
            <li key={item.id} className={`photo-item ${item.state}`}>
              <img src={item.preview} alt={item.file.name} />
              <span className="photo-name">{item.file.name}</span>
              {item.state === "done" ? (
                <CircleCheck className="photo-ok" />
              ) : item.state === "failed" ? (
                <span className="photo-error" title={item.error}>
                  <TriangleAlert /> Failed
                </span>
              ) : item.state === "uploading" ? (
                <span className="photo-progress">Uploading…</span>
              ) : (
                <button
                  type="button"
                  className="photo-remove"
                  onClick={() => remove(item.id)}
                  aria-label={`Remove ${item.file.name}`}
                >
                  <X />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
