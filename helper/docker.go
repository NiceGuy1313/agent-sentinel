package helper

import (
	"context"
	"fmt"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/client"
)

var apiClient, _ = client.NewClientWithOpts(client.FromEnv)

func QueryPIDFromContainerID(cid string) (int, error) {
	if apiClient == nil {
		return 0, fmt.Errorf("docker api client is nil")
	}

	cjson, err := apiClient.ContainerInspect(context.Background(), cid)
	if err != nil {
		return 0, err
	}

	return cjson.State.Pid, nil
}

func QueryFullIDFromContainerID(cid string) (string, error) {
	if apiClient == nil {
		return "", fmt.Errorf("docker api client is nil")
	}

	cjson, err := apiClient.ContainerInspect(context.Background(), cid)
	if err != nil {
		return "", err
	}

	return cjson.ID, nil
}

func QueryNetworkNameFromContainerID(cid string) (string, error) {
	if apiClient == nil {
		return "", fmt.Errorf("docker api client is nil")
	}

	cjson, err := apiClient.ContainerInspect(context.Background(), cid)
	if err != nil {
		return "", err
	}

	// fixme: multiple networks?
	netID, ok := cjson.NetworkSettings.Networks["bridge"]
	if !ok {
		return "", fmt.Errorf("network id not found")
	}

	netIns, err := apiClient.NetworkInspect(context.Background(), netID.NetworkID, network.InspectOptions{})
	if err != nil {
		return "", err
	}

	return netIns.Options["com.docker.network.bridge.name"], nil
}

func GetBaseBashBinaryPathFromContainerID(cid string) (string, error) {
	if apiClient == nil {
		return "", fmt.Errorf("docker api client is nil")
	}

	cjson, err := apiClient.ContainerInspect(context.Background(), cid)
	if err != nil {
		return "", err
	}

	return cjson.GraphDriver.Data["MergedDir"] + "/bin/bash", nil
}
